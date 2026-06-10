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
VIRTUAL_BOT_JSON = DATA_REPO / "current" / "Objects" / "VirtualBot.json"
MODULE_TYPE_JSON = DATA_REPO / "current" / "Objects" / "ModuleType.json"
CHARACTER_PRESET_JSON = DATA_REPO / "current" / "Objects" / "CharacterPreset.json"


PROMPT_DIR = SCRIPT_DIR / "prompt"
OUTPUT_DIR = PROMPT_DIR / "output"

SCRAPED_PAGE = PROMPT_DIR / "scraped_news_page.txt"
GAME_DATA_JSON = PROMPT_DIR / "game_data.json"
ITEM_NAMES_INPUT = PROMPT_DIR / "item_names.txt"
DISCOUNTS_OUTPUT = OUTPUT_DIR / "discounts.json"

FRONTEND_DATA_DIR = REPO_ROOT / "src" / "frontend" / "public" / "data"
WEEKS_MANIFEST = FRONTEND_DATA_DIR / "weeks.json"
REVERSE_LOOKUP_OUTPUT = FRONTEND_DATA_DIR / "discount_reverse_lookup.json"

def date_range_to_slug(date_range: str) -> str:
    """Convert a legacy date range to the start-date slug used for week filenames."""
    from week_dates import normalize_week, week_slug
    return week_slug(normalize_week(date_range))

# Module groups that appear as standalone discountable items (weapons / gear).
# step2 INCLUDES only these groups when building game_data for the LLM.
# step4 EXCLUDES these groups when expanding a VirtualBot's core_module_refs,
# so titan-specific weapons don't bleed into robot frame listings.
STANDALONE_MODULE_GROUPS = [
    "supply-gear",
    "cycle-gear",
    "light-weapon",
    "heavy-weapon",
    "titan-weapon",
]

