from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
TELEGRAM_API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
GSPREAD_SHEET_CREDENTIALS = os.getenv("GSPREAD_SHEET_CREDENTIALS")
SHEET_ID = os.getenv("SHEET_ID")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")