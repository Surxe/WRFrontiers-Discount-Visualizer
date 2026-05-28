"""
fetch_discounts.py

Backend orchestrator for WRFrontiers Discount Visualizer.

Usage:
    python fetch_discounts.py <news_url>

Example:
    python fetch_discounts.py https://warrobotsfrontiers.com/en/news/272-intel-salvage-discount-event-save-big-april-14-21

Steps:
    1. Scrape the news URL and save body text to prompt/scraped_news_page.txt
    2. Load WRFrontiersDB-Data/current/Objects/Module.json and build game_data.json
    3. Call the Gemini CLI with access to prompt/ directory to map items
    4. Read the LLM output from prompt/output/discounts.json
    5. Copy referenced images to src/frontend/public/assets/ (preserving paths)
    6. Copy discounts.json to src/frontend/public/data/discounts.json
"""

import sys
import os
import json
import re
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────

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
    DATA_REPO = _data_repo_local  # will fail gracefully with a clear error later

MODULE_JSON = DATA_REPO / "current" / "Objects" / "Module.json"
TEXTURES_DIR = DATA_REPO / "textures"

PROMPT_DIR = SCRIPT_DIR / "prompt"
OUTPUT_DIR = PROMPT_DIR / "output"

SCRAPED_PAGE = PROMPT_DIR / "scraped_news_page.txt"
GAME_DATA_JSON = PROMPT_DIR / "game_data.json"
DISCOUNTS_OUTPUT = OUTPUT_DIR / "discounts.json"

FRONTEND_DATA_DIR = REPO_ROOT / "src" / "frontend" / "public" / "data"
FRONTEND_ASSETS_DIR = REPO_ROOT / "src" / "frontend" / "public" / "assets"

# ─────────────────────────────────────────────
# Step 1: Scrape the URL
# ─────────────────────────────────────────────

def scrape_url(url: str) -> str:
    """
    Downloads the news page and extracts the article body text.
    The site uses Nuxt SSR and embeds the article body in JSON-LD structured data.
    Falls back to BeautifulSoup body text if JSON-LD is not found.
    """
    print(f"[1/5] Scraping URL: {url}")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Try JSON-LD first (most reliable for this SSR site)
    for script_tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script_tag.string)
            if isinstance(data, dict) and "articleBody" in data:
                article_html = data["articleBody"]
                # Strip HTML tags from article body
                article_soup = BeautifulSoup(article_html, "html.parser")
                return article_soup.get_text(separator="\n").strip()
        except (json.JSONDecodeError, TypeError):
            continue

    # Fallback: extract all visible text from the page body
    print("  [!] JSON-LD not found; falling back to body text extraction.")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n").strip()


def save_scraped_page(text: str):
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    SCRAPED_PAGE.write_text(text, encoding="utf-8")
    print(f"  -> Saved scraped text to {SCRAPED_PAGE.relative_to(REPO_ROOT)}")


# ─────────────────────────────────────────────
# Step 2: Build game_data.json from Module.json
# ─────────────────────────────────────────────

def build_game_data() -> list[dict]:
    """
    Reads Module.json and extracts all production-ready modules.
    Produces a compact list of { id, name, image_path } for the LLM prompt.

    image_path is derived from inventory_icon_path, which looks like:
        /WRFrontiers/Content/Sparrow/UI/Textures/Modules/T_Module_ChassisAres
    We strip the leading '/' to get a relative path usable to locate the file
    inside the textures/ directory.
    """
    print(f"[2/5] Building game_data.json from {MODULE_JSON}")

    if not MODULE_JSON.exists():
        print(f"  [ERROR] Module.json not found at {MODULE_JSON}")
        print(
            "  Make sure WRFrontiersDB-Data is cloned. "
            "Set DATA_REPO_PAT in .env and run:\n"
            "  git clone https://<PAT>@github.com/Surxe/WRFrontiersDB-Data.git WRFrontiersDB-Data"
        )
        sys.exit(1)

    with open(MODULE_JSON, encoding="utf-8") as f:
        modules = json.load(f)

    game_data = []
    skipped = 0

    for module_id, module in modules.items():
        # Only include production-ready modules
        if module.get("production_status") != "Ready":
            skipped += 1
            continue

        # Extract English name
        name_field = module.get("name", {})
        english_name = name_field.get("en", "")
        if not english_name:
            skipped += 1
            continue

        # Extract image path — strip leading '/' to make it relative
        icon_path = module.get("inventory_icon_path", "")
        if not icon_path:
            skipped += 1
            continue

        # Normalize: strip leading '/' 
        image_path = icon_path.lstrip("/")

        game_data.append({
            "id": module_id,
            "name": english_name,
            "image_path": image_path,
        })

    print(f"  -> {len(game_data)} production modules found ({skipped} skipped)")
    return game_data


def save_game_data(game_data: list[dict]):
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    with open(GAME_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(game_data, f, indent=2, ensure_ascii=False)
    print(f"  -> Saved to {GAME_DATA_JSON.relative_to(REPO_ROOT)}")


# ─────────────────────────────────────────────
# Step 3: Call the Gemini CLI
# ─────────────────────────────────────────────

def call_gemini_cli():
    """
    Invokes the Gemini CLI via subprocess.
    The CLI is given access to the prompt/ directory and instructed to follow prompt.md.
    It should write output to prompt/output/discounts.json.
    """
    print("[3/5] Calling Gemini CLI...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build the prompt message that references the files
    prompt_message = (
        "Follow the instructions in prompt.md. "
        "Read scraped_news_page.txt and game_data.json from the current directory, "
        "then write the output JSON array to output/discounts.json."
    )

    # Try 'gemini' (globally installed) then fall back to npx
    gemini_cmd = shutil.which("gemini")
    if gemini_cmd:
        cmd = [gemini_cmd, "--skip-trust", "--prompt", prompt_message]
    else:
        cmd = ["npx", "--yes", "@google/gemini-cli", "--skip-trust", "--prompt", prompt_message]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROMPT_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  [ERROR] Gemini CLI exited with code {result.returncode}")
            print(f"  STDOUT: {result.stdout}")
            print(f"  STDERR: {result.stderr}")
            sys.exit(1)
        print(f"  -> Gemini CLI completed successfully.")
        if result.stdout:
            print(f"  STDOUT: {result.stdout[:500]}")
    except FileNotFoundError:
        print(
            "  [ERROR] 'gemini' CLI not found. "
            "Install it with: npm install -g @google/gemini-cli"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("  [ERROR] Gemini CLI timed out after 120 seconds.")
        sys.exit(1)


# ─────────────────────────────────────────────
# Step 4: Read LLM output
# ─────────────────────────────────────────────

def load_discounts() -> list[dict]:
    """
    Reads the LLM-generated discounts.json output.
    Validates that it is a non-empty list with the expected fields.
    """
    print("[4/5] Reading LLM output from prompt/output/discounts.json...")

    if not DISCOUNTS_OUTPUT.exists():
        print(f"  [ERROR] Output file not found: {DISCOUNTS_OUTPUT}")
        print("  The Gemini CLI may not have written the output file.")
        sys.exit(1)

    with open(DISCOUNTS_OUTPUT, encoding="utf-8") as f:
        content = f.read().strip()

    # Strip markdown code fences if the LLM wrapped the JSON
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        discounts = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  [ERROR] Output is not valid JSON: {e}")
        print(f"  Content preview: {content[:300]}")
        sys.exit(1)

    if not isinstance(discounts, list) or len(discounts) == 0:
        print("  [ERROR] Output is empty or not a JSON array.")
        sys.exit(1)

    print(f"  -> {len(discounts)} discounted items found:")
    for item in discounts:
        print(f"     • {item.get('name', '?')} ({item.get('id', '?')})")

    return discounts


# ─────────────────────────────────────────────
# Step 5: Copy images and output to frontend
# ─────────────────────────────────────────────

def copy_assets(discounts: list[dict]):
    """
    For each item in discounts, copies its image from the textures directory
    to src/frontend/public/assets/, preserving the original directory structure.

    The image_path from Module.json looks like:
        WRFrontiers/Content/Sparrow/UI/Textures/Modules/T_Module_ChassisAres

    The actual file on disk is at:
        WRFrontiersDB-Data/textures/WRFrontiers/Content/.../T_Module_ChassisAres.png

    We look for the file with a .png extension (common format in the textures dir).
    """
    print("[5/5] Copying images to frontend assets...")

    FRONTEND_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing = []

    for item in discounts:
        image_path = item.get("image_path", "")
        if not image_path:
            continue

        # Source: look for .png file in textures directory
        src_file = TEXTURES_DIR / (image_path + ".png")

        if not src_file.exists():
            missing.append(image_path)
            print(f"  [!] Image not found: {src_file.relative_to(REPO_ROOT)}")
            continue

        # Destination: same relative path under frontend/public/assets/
        dst_file = FRONTEND_ASSETS_DIR / (image_path + ".png")
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied += 1
        print(f"  -> Copied: {image_path}.png")

    print(f"  -> {copied} images copied, {len(missing)} missing.")


def copy_discounts_to_frontend(discounts: list[dict]):
    """Writes the final discounts.json to the frontend public/data directory."""
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dst = FRONTEND_DATA_DIR / "discounts.json"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(discounts, f, indent=2, ensure_ascii=False)
    print(f"  -> Copied discounts.json to {dst.relative_to(REPO_ROOT)}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_discounts.py <news_url>")
        print(
            "Example: python fetch_discounts.py "
            "https://warrobotsfrontiers.com/en/news/272-intel-salvage-discount-event-save-big-april-14-21"
        )
        sys.exit(1)

    url = sys.argv[1]

    # Step 1: Scrape
    article_text = scrape_url(url)
    save_scraped_page(article_text)

    # Step 2: Build game data
    game_data = build_game_data()
    save_game_data(game_data)

    # Step 3: Call LLM
    call_gemini_cli()

    # Step 4: Load output
    discounts = load_discounts()

    # Step 5: Copy assets
    copy_assets(discounts)
    copy_discounts_to_frontend(discounts)

    print("\n✅ Done! discounts.json is ready in src/frontend/public/data/")


if __name__ == "__main__":
    main()
