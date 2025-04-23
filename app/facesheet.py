import os
import sys
import json

from dotenv import load_dotenv
from googleapiclient.http import MediaFileUpload
from jinja2 import Environment, FileSystemLoader

from pdf import convert_html_to_pdf
from logger import log_message
from config import IS_PRODUCTION, PARENT_FOLDER
from google_auth_helper import get_drive_service, get_sheet
from images_helper import initialize_image_index, check_image_exists
from sheet import fetch_pdf_settings, generate_grouped_people
from core import app

# === Environment Setup ===
if not IS_PRODUCTION:
    load_dotenv()

# === Config ===
TEMPLATE_DIR = "templates"

drive_service = get_drive_service()

# === Drive Upload ===
def upload_or_replace_file(file_path, filename, parent_id, mime_type="application/pdf"):
    """Uploads a file to Drive, replacing the old one if it exists."""
    try:
        existing = drive_service.files().list(
            q=f"'{parent_id}' in parents and name='{filename}' and trashed=false",
            fields="files(id)"
        ).execute().get('files', [])

        for f in existing:
            try:
                drive_service.files().delete(fileId=f['id']).execute()
                log_message(f"🗑️ Deleted old {filename}")
            except Exception as e:
                log_message(f"⚠️ Failed to delete {filename}: {e}")

        metadata = {
            'name': filename,
            'parents': [parent_id],
            'mimeType': mime_type
        }
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True, chunksize=5 * 1024 * 1024)
        upload = drive_service.files().create(body=metadata, media_body=media, fields='id').execute()

        file_link = f"https://drive.google.com/file/d/{upload['id']}/view"
        log_message(f"✅ Uploaded file: {file_link}")
        return upload['id'], file_link

    except Exception as e:
        log_message(f"❌ Upload error: {e}")
        return None, None

# === Helpers ===
def return_response(payload):
    if not IS_PRODUCTION:
        print("\n🛠️  [DEV MODE OUTPUT]")
        print(json.dumps(payload, indent=2))
        print("🛠️  [END OUTPUT]\n")
    return payload

# === Main Workflow ===
def generate(email, sheet_id):
    log_message(f"👤 Starting generation for {email} using sheet ID: {sheet_id}")
    try:
        sheet = get_sheet(sheet_id)
        log_message(f"📄 Using Google Sheet: '{sheet.title}'")

        OUTPUT_HTML = f"{sheet.title}.html"
        OUTPUT_PDF = f"{sheet.title}.pdf"

        settings_data, size, top, bottom = fetch_pdf_settings(sheet)
        log_message("⚙️ PDF settings fetched.")

        initialize_image_index()

        grouped_people = generate_grouped_people(sheet)
        log_message(f"🧑‍🤝‍🧑 Grouped data for {len(grouped_people)} groups.")

        logo_path = check_image_exists("logo")
        log_message(f"🖼️ Logo path: {logo_path}")

        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        tpl = env.get_template("facesheet.html")
        html = tpl.render(
            settings_data=settings_data,
            grouped_people=grouped_people,
            email=email,
            logo_path=logo_path
        )

        with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
            f.write(html)
        log_message(f"✍️ HTML written to: {OUTPUT_HTML}")

        log_message("🚧 Starting PDF generation...")
        convert_html_to_pdf(OUTPUT_HTML, OUTPUT_PDF, size, top, bottom)

        file_id, file_link = upload_or_replace_file(OUTPUT_PDF, OUTPUT_PDF, PARENT_FOLDER)
        log_message(f"📤 PDF uploaded to Drive. Link: {file_link}")

        payload = {"result": "Success", "pdf_link": file_link}
        if not IS_PRODUCTION:
            return_response(payload)
        return payload

    except Exception as e:
        error_payload = {"result": "Error", "error": str(e)}
        log_message(f"🔥 Error during generation: {e}")
        if not IS_PRODUCTION:
            return_response(error_payload)
        return error_payload

# === CLI Entrypoint ===
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python facesheet.py <email> <sheet_id>")
        sys.exit(1)
    generate(sys.argv[1], sys.argv[2])
