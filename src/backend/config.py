"""
config.py

Shared configuration and path definitions for the backend scripts.
"""

from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

# WRFrontiersDB-Data can be cloned either:
#   1. Inside this project root (preferred, per design doc)
#   2. As a sibling repo next to this project (local dev convenience)
_data_repo_local = REPO_ROOT / "WRFrontiersDB-Data"
_data_repo_sibling = REPO_ROOT.parent / "WRFrontiersDB-Data"

if _data_repo_local.exists():
    DATA_REPO = _data_repo_local
elif _data_repo_sibling.exists():
    DATA_REPO = _data_repo_sibling
    print(f"[INFO] Using sibling WRFrontiersDB-Data at {DATA_REPO}")
else:
    DATA_REPO = _data_repo_local

MODULE_JSON = DATA_REPO / "current" / "Objects" / "Module.json"
TEXTURES_DIR = DATA_REPO / "textures"

PROMPT_DIR = SCRIPT_DIR / "prompt"
OUTPUT_DIR = PROMPT_DIR / "output"

SCRAPED_PAGE = PROMPT_DIR / "scraped_news_page.txt"
GAME_DATA_JSON = PROMPT_DIR / "game_data.json"
DISCOUNTS_OUTPUT = OUTPUT_DIR / "discounts.json"

FRONTEND_DATA_DIR = REPO_ROOT / "src" / "frontend" / "public" / "data"
FRONTEND_ASSETS_DIR = REPO_ROOT / "src" / "frontend" / "public" / "assets"
