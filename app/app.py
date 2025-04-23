import os
import io
import sys
import shutil
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, session, request, redirect, url_for, jsonify, Response
from flask_socketio import SocketIO, emit
from flask_session import Session
from flask_cors import CORS

from auth import login, logout, check_login, setup_oauth, authorized, ALLOWED_EMAILS
from facesheet import generate as generate_facesheet
from utils import log_message

# === Load environment variables ===
load_dotenv()
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
BASE_URL = os.getenv("LOCAL_URL") if ENVIRONMENT == "development" else os.getenv("BASE_URL")
PORT = int(os.getenv('PORT', 8080))

# === Flask App Setup ===
app = Flask(__name__, template_folder='../templates')
app.config['BASE_URL'] = BASE_URL
app.secret_key = 'super_secure_secret_key'

# CORS
CORS(app, origins=[
    "https://facesheet-frontend.storage.googleapis.com",
    "http://localhost:5000"
])

# === Session Setup ===
SESSION_FOLDER = os.path.join(os.getcwd(), 'flask_session')
if os.path.exists(SESSION_FOLDER):
    shutil.rmtree(SESSION_FOLDER)
os.makedirs(SESSION_FOLDER, exist_ok=True)

app.config.update({
    'SESSION_TYPE': 'filesystem',
    'SESSION_FILE_DIR': SESSION_FOLDER,
    'SESSION_PERMANENT': True,
    'PERMANENT_SESSION_LIFETIME': timedelta(days=7)
})
Session(app)

# === OAuth & SocketIO ===
setup_oauth(app)
socketio = SocketIO(app)

# === Routes ===

@app.route('/')
def home():
    if 'email' in session:
        return render_template('home.html', email=session.get('email'))
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        if not email or "@" not in email:
            error = "Please enter a valid email address."
        else:
            session['submitted_email'] = email.strip().lower()
            return login()  # Should trigger Google OAuth flow
    return render_template('login.html', error=error)

@app.route('/precheck_email', methods=['POST'])
def precheck_email():
    submitted_email = request.form.get('email', '').strip().lower()
    print(f"Submitted Email: {submitted_email}")
    if submitted_email in ALLOWED_EMAILS:
        session['submitted_email'] = submitted_email
        return login()
    else:
        error = f"🚫 Email {submitted_email} is not allowed."
        return render_template('login.html', error=error)

@app.route('/login/authorized')
def authorized_route():
    return authorized()

@app.route('/logout')
def logout_route():
    session.clear()
    return redirect(url_for('login_page'))

@app.route("/me")
def me():
    return jsonify({"email": session.get("email")})

@app.route('/generate', methods=['POST'])
def rerun_generate():
    if 'email' not in session:
        return redirect(url_for('login_page'))

    try:
        socketio.emit('log', {'message': 'Generation started...'})

        result = generate_facesheet(email=session['email'], socketio=socketio)

        if isinstance(result, Response):
            result_data = result.get_json()
        else:
            result_data = result

        pdf_link = result_data.get('pdf_link')
        message = f"🎉 All done! PDF Link: {pdf_link}" if pdf_link else "❌ Failed to generate PDF link."
        socketio.emit('log', {'message': message})

        return jsonify({
            'result': 'Generation Complete' if pdf_link else 'Error',
            'pdf_link': pdf_link
        })

    except Exception as e:
        error_message = f"❌ Error during generation: {e}"
        socketio.emit('log', {'message': error_message})
        return jsonify({'result': 'Error', 'pdf_link': None})

# === Socket.IO Events ===

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# === Main Entry Point ===
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=PORT, debug=True)
