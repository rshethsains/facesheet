import os
import io
import sys
import json
import subprocess
import unicodedata

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from oauth2client.service_account import ServiceAccountCredentials
from jinja2 import Environment, FileSystemLoader
from flask import jsonify
import gspread

import pdf  # assumes pdf.py is in the same directory or properly importable
from utils import log_message  # assumes you have a utils.py with log_message()

# === Load env ===
load_dotenv()

log_buffer = io.StringIO()
sys.stdout = log_buffer

ENV = os.getenv("ENVIRONMENT", "development")

# === Config from .env ===
PARENT_FOLDER = os.getenv("PARENT_FOLDER")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
IMAGE_DRIVE_FOLDER_ID = os.getenv("IMAGE_DRIVE_FOLDER_ID")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE")
IMAGES_DIR = os.getenv("IMAGES_DIR")
TEMPLATE_DIR = os.getenv("TEMPLATE_DIR")
OUTPUT_HTML = os.getenv("OUTPUT_HTML")
OUTPUT_PDF = os.getenv("OUTPUT_PDF")

# === Google Setup ===
scope = [
    "https://www.googleapis.com/auth/drive.file",
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
gclient = gspread.authorize(creds)
sheet = gclient.open_by_key(GOOGLE_SHEET_ID)
drive_service = build('drive', 'v3', credentials=creds)


def fetch_pdf_settings():
    settings = sheet.worksheet("Settings").get_all_values()
    settings_data = {row[0]: row[1] for row in settings[1:] if row[0]}
    return settings_data, settings_data.get("PDFSize", "A4"), settings_data.get("TopMargin", "0.5in"), settings_data.get("BottomMargin", "0.5in")


def check_image_exists(image_dir, base_name):
    base_name_normalized = unicodedata.normalize('NFKD', base_name).lower()
    for fname in os.listdir(image_dir):
        name, ext = os.path.splitext(fname)
        name_normalized = unicodedata.normalize('NFKD', name).lower()
        if ext.lower() in ('.png', '.jpg', '.jpeg') and name_normalized == base_name_normalized:
            return os.path.join(image_dir, fname)
    return None


def download_images(socketio=None):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    files = drive_service.files().list(
        q=f"'{IMAGE_DRIVE_FOLDER_ID}' in parents and trashed=false",
        fields="files(id,name,mimeType,size)"
    ).execute().get('files', [])

    log_message(f"🔍 Found {len(files)} images in Drive folder.", socketio)
    for f in files:
        title, mime, fid = f['name'], f['mimeType'], f['id']
        if not mime.startswith("image/"):
            continue
        log_message(f"⬇️ Checking {title}", socketio)
        local = check_image_exists(IMAGES_DIR, os.path.splitext(title)[0])
        if local:
            remote_size = int(drive_service.files().get(fileId=fid, fields="size").execute()['size'])
            if os.path.getsize(local) == remote_size:
                log_message(f"✅ {title} up-to-date.", socketio)
                continue
            log_message(f"⚠️ {title} size mismatch, re-downloading...", socketio)

        log_message(f"⬇️ Downloading {title}", socketio)
        out_path = os.path.join(IMAGES_DIR, title)
        req = drive_service.files().get_media(fileId=fid)
        with open(out_path, 'wb') as fh:
            dl = MediaIoBaseDownload(fh, req)
            done = False
            while not done:
                status, done = dl.next_chunk()
                log_message(f"   → {int(status.progress() * 100)}%", socketio)
        log_message(f"✅ Finished {title}", socketio)


def generate_grouped_people():
    rows = sheet.worksheet("People").get_all_values()[1:]
    people = []
    for r in rows:
        if not any(cell.strip() for cell in r):
            continue
        name = r[1]
        img = check_image_exists(IMAGES_DIR, name.replace(" ", "_"))
        people.append({
            "Category": "" if r[0].upper() == "N/A" else r[0],
            "Name": name,
            "Title": r[2],
            "Show": r[3] if len(r) > 3 else "",
            "Image File": img or "image_not_found.png"
        })

    grouped = {}
    for p in people:
        grouped.setdefault(p["Category"], []).append(p)
    return grouped


def generate_pdf_in_subprocess(html_file, pdf_file, size, top, bottom, socketio=None):
    pdf_path = os.path.join(os.path.dirname(__file__), "pdf.py")
    cmd = ["python", pdf_path, html_file, pdf_file, size, top, bottom]
    process = subprocess.run(cmd, capture_output=True, text=True)
    if socketio:
        if process.stdout:
            log_message(process.stdout, socketio)
        if process.stderr:
            log_message(process.stderr, socketio)
    if process.returncode != 0:
        raise RuntimeError("PDF generation failed.")
    else:
        log_message("📄 PDF generated successfully", socketio)


def upload_or_replace_pdf(pdf_path, filename, parent_id, socketio=None):
    try:
        existing_files = drive_service.files().list(
            q=f"'{parent_id}' in parents and name='{filename}' and trashed=false",
            fields="files(id)"
        ).execute().get('files', [])
        for old in existing_files:
            drive_service.files().delete(fileId=old['id']).execute()
            log_message(f"🗑️ Deleted old {filename}", socketio)

        file_metadata = {
            'name': filename,
            'parents': [parent_id],
            'mimeType': 'application/pdf'
        }
        media = MediaFileUpload(pdf_path, mimetype='application/pdf')
        uploaded = drive_service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()

        file_id = uploaded['id']
        file_link = f"https://drive.google.com/file/d/{file_id}/view"
        log_message(f"✅ Uploaded PDF: {file_link}", socketio)
        return file_id, file_link
    except Exception as e:
        log_message(f"❌ Upload error: {e}", socketio)
        return None, None


def return_response(payload):
    if ENV == "production":
        return jsonify(payload)
    else:
        print("\n🛠️  [DEV MODE OUTPUT]")
        print(json.dumps(payload, indent=2))
        print("🛠️  [END OUTPUT]\n")
        return payload


def generate(email, socketio=None):
    log_message(f"👤 Starting generation for {email}", socketio)
    try:
        settings_data, pdf_size, top_margin, bottom_margin = fetch_pdf_settings()
        download_images(socketio=socketio)

        logo_path = check_image_exists(IMAGES_DIR, "logo") or "image_not_found.png"
        if logo_path == "image_not_found.png":
            log_message("⚠️ Logo not found, using fallback", socketio)

        gp = generate_grouped_people()
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        tpl = env.get_template("facesheet.html")
        html = tpl.render(
            settings_data=settings_data,
            image_dir=IMAGES_DIR,
            grouped_people=gp,
            email=email,
            logo_path=logo_path
        )

        with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
            f.write(html)
        log_message(f"✅ HTML generated at {OUTPUT_HTML}", socketio)

        generate_pdf_in_subprocess(OUTPUT_HTML, OUTPUT_PDF, pdf_size, top_margin, bottom_margin, socketio)

        file_id, file_link = upload_or_replace_pdf(OUTPUT_PDF, OUTPUT_PDF, PARENT_FOLDER, socketio=socketio)
        result = {
            'result': 'Success',
            'logs': log_buffer.getvalue(),
            'pdf_link': file_link
        }

    except Exception as e:
        error_msg = f"🔥 Error during generation: {e}"
        log_message(error_msg, socketio)
        result = {
            'result': 'Error',
            'logs': log_buffer.getvalue(),
            'error': error_msg
        }

    finally:
        sys.stdout = sys.__stdout__

    return return_response(result)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python facesheet.py <email>")
        sys.exit(1)
    email = sys.argv[1]
    generate(email)
