"""
step2_build_game_data.py

Step 2: Load WRFrontiersDB-Data/current/Objects/Module.json and build game_data.json.
"""

import sys
import json
from config import MODULE_JSON, PROMPT_DIR, GAME_DATA_JSON, REPO_ROOT

def build_game_data() -> list[dict]:
    """
    Reads Module.json and extracts all production-ready modules.
    Produces a compact list of { id, name, image_path } for the LLM prompt.

    image_path is derived from inventory_icon_path, which looks like:
        /WRFrontiers/Content/Sparrow/UI/Textures/Modules/T_Module_ChassisAres
    We strip the leading '/' to get a relative path usable to locate the file
    inside the textures/ directory.
    """
    print(f"[2/4] Building game_data.json from {MODULE_JSON}")

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


def run_step():
    game_data = build_game_data()
    save_game_data(game_data)


if __name__ == "__main__":
    run_step()
