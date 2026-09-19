"""
config.py

Shared configuration and path definitions for the backend scripts.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Jev name->id mapping (see jev_mapper.py) --------------------------------
# TypeSafe AI's Jev classifier maps announced item names to game_data refs.
# JEV_API_KEY is provided as a repo secret in CI; when unset the mapper is
# disabled and step2 falls back to local difflib fuzzy matching (offline mode).
JEV_API_KEY = os.environ.get("JEV_API_KEY") or None
JEV_MODEL = os.environ.get("JEV_MODEL") or None  # None -> SDK default (jev-latest)
JEV_ACCEPT_THRESHOLD = float(os.environ.get("JEV_ACCEPT_THRESHOLD", "0.7"))
JEV_SPLIT_PIECE_THRESHOLD = float(os.environ.get("JEV_SPLIT_PIECE_THRESHOLD", "0.75"))

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
VIRTUAL_BOT_JSON = DATA_REPO / "current" / "Objects" / "VirtualBot.json"
MODULE_TYPE_JSON = DATA_REPO / "current" / "Objects" / "ModuleType.json"
CHARACTER_PRESET_JSON = DATA_REPO / "current" / "Objects" / "CharacterPreset.json"


TEMP_DIR = SCRIPT_DIR / "temp"
OUTPUT_DIR = TEMP_DIR / "output"

GAME_DATA_JSON = SCRIPT_DIR / "game_data" / "game_data.json"
MANUAL_MAPPING_JSON = SCRIPT_DIR / "manual_mapping.json"
DISCOUNTS_OUTPUT = OUTPUT_DIR / "discounts.json"

FRONTEND_DATA_DIR = REPO_ROOT / "src" / "frontend" / "public" / "data"
WEEKS_MANIFEST = FRONTEND_DATA_DIR / "weeks.json"
REVERSE_LOOKUP_OUTPUT = FRONTEND_DATA_DIR / "discount_data.json"
PREDICTIONS_OUTPUT = FRONTEND_DATA_DIR / "predictions.json"
ACCURACY_HISTORY_OUTPUT = FRONTEND_DATA_DIR / "accuracy_history.json"
# Per-week frozen prediction snapshots + their index (the /history page).
PREDICTION_HISTORY_DIR = FRONTEND_DATA_DIR / "predictions_history"
PREDICTION_HISTORY_INDEX = PREDICTION_HISTORY_DIR / "index.json"

def date_range_to_slug(date_range: str) -> str:
    """Convert a legacy date range to the start-date slug used for week filenames."""
    from week_dates import normalize_week, week_slug
    return week_slug(normalize_week(date_range))

# Module groups that appear as standalone discountable items (weapons / gear).
# step1 INCLUDES only these groups when building game_data.
# step2 EXCLUDES titan-weapon when expanding a VirtualBot's core_module_refs,
# so titan-specific weapons don't bleed into robot frame listings.
STANDALONE_MODULE_GROUPS = [
    "supply-gear",
    "cycle-gear",
    "light-weapon",
    "heavy-weapon",
    "titan-weapon",
]

