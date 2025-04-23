import os

# Environment info
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"
PARENT_FOLDER = os.getenv("PARENT_FOLDER")

# Base URL and port
PORT = int(os.getenv("PORT", 8080))
BASE_URL = os.getenv("BASE_URL") if IS_PRODUCTION else f"http://localhost:{PORT}"
