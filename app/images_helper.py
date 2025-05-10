import os
import unicodedata
from dotenv import load_dotenv

from logger import log_message
from google_auth_helper import get_drive_service

# === Environment Setup ===
load_dotenv()

# Drive service
drive_service = get_drive_service()

# Global index
_image_index = {}

def initialize_image_index(IMAGE_DRIVE_FOLDER_ID):
    """Fetch all image names from Google Drive and normalize to lowercase."""
    global _image_index
    _image_index = {}  # Reset index each run
    log_message("🔄 Initializing image index from Google Drive...")

    try:
        page_token = None
        while True:
            response = drive_service.files().list(
                q=f"'{IMAGE_DRIVE_FOLDER_ID}' in parents and trashed=false",
                fields="nextPageToken, files(id, name)",
                pageSize=1000,
                pageToken=page_token
            ).execute()

            for item in response.get('files', []):
                name = item['name']
                file_id = item['id']
                norm_key = unicodedata.normalize('NFKD', name).lower()
                _image_index[norm_key] = f"https://lh3.googleusercontent.com/d/{file_id}=s220?authuser=0"

            page_token = response.get('nextPageToken')
            if not page_token:
                break

        log_message(f"✅ Indexed {len(_image_index)} images from Google Drive.")
    except Exception as e:
        log_message(f"⚠️ Error indexing images from Drive: {e}")
        _image_index = {}


def check_image_exists(image_name):
    """Look up the image in the normalized index with common extensions."""
    norm_name = unicodedata.normalize('NFKD', image_name).lower()

    for ext in ['.png', '.jpg', '.jpeg']:
        key = f"{norm_name}{ext}"
        if key in _image_index:
            return _image_index[key]

    log_message(f"❌ '{norm_name}' not found in Drive image index.")
    return None