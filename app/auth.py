from flask import redirect, session, url_for, jsonify, render_template, request
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import os
import requests

# Load .env variables
load_dotenv()

# OAuth setup
oauth = OAuth()
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile', 'prompt': 'select_account'}
)

# Load allowed emails from .env and split into a set
ALLOWED_EMAILS = set(os.getenv("ALLOWED_EMAILS", "").split(','))

# Check if running in local development or production
environment = os.getenv("ENVIRONMENT", "development")

if environment == "development":
    base_url = os.getenv("LOCAL_URL", "http://localhost:8080")
else:
    base_url = os.getenv("BASE_URL", "https://your-app-url.a.run.app")

continue_url = base_url
oauth_redirect_uri = f"{base_url}/login/authorized"
def setup_oauth(app):
    """Configure OAuth with the app."""
    oauth.init_app(app)

def login():
    """Redirect to Google's OAuth login."""
    session.clear()
    submitted_email = request.form.get('email')  # Or however you get the email from the form
    if submitted_email:
        session['submitted_email'] = submitted_email.strip().lower()
    return google.authorize_redirect(redirect_uri=oauth_redirect_uri)

def logout():
    """Clear session and log the user out of Google OAuth."""
    session.clear()
    google.logout()
    return redirect(f"https://accounts.google.com/Logout?continue=https://appengine.google.com/_ah/logout?continue={continue_url}")

def authorized():
    """Handle the OAuth callback and verify email."""
    token = google.authorize_access_token()

    # Get user info from Google OAuth
    user_info = token.get('userinfo') or google.get('userinfo').json()
    oauth_email = user_info.get('email').strip().lower()  # Normalize the email from OAuth
    submitted_email = session.get('submitted_email', '').strip().lower()  # Normalize the submitted email

    # Debugging: Print the emails being compared
    print(f"OAuth Email: {oauth_email}")
    print(f"Submitted Email: {submitted_email}")

    # Check if the OAuth email matches the submitted email
    if oauth_email != submitted_email:
        return render_template('login.html', error=f"⚠️ OAuth email ({oauth_email}) does not match submitted email ({submitted_email}).")

    # Check if the email is allowed
    if oauth_email in ALLOWED_EMAILS:
        session['email'] = oauth_email  # Store the email in the session
        return redirect(url_for('home'))
    else:
        return render_template('login.html', error=f"🚫 Access denied for {oauth_email}.")

def revoke_google_token():
    """Revoke the user's Google OAuth token."""
    token = session.get('oauth_token')
    if token:
        try:
            response = requests.post(f"https://oauth2.googleapis.com/revoke?token={token['access_token']}")
            if response.status_code == 200:
                print("Google OAuth token revoked successfully.")
            else:
                print(f"Failed to revoke token: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error revoking token: {e}")

def check_login():
    """Check if the user is logged in."""
    if 'email' in session:
        return True  # User is logged in
    return False  # User is not logged in
