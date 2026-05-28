"""
step2_build_game_data.py

Step 2: Load WRFrontiersDB-Data/current/Objects/Module.json and build game_data.json.
"""

import sys
import json
from config import MODULE_JSON, VIRTUAL_BOT_JSON, PROMPT_DIR, GAME_DATA_JSON, REPO_ROOT

def build_game_data() -> list[dict]:
    """
    Reads VirtualBot.json and Module.json to extract relevant game objects.
    Produces a compact list of { id, name, image_path } for the LLM prompt.
    VirtualBots are prefixed with OBJID_VirtualBot::
    Modules are prefixed with OBJID_Module::
    """
    print(f"[2/4] Building game_data.json...")

    if not MODULE_JSON.exists() or not VIRTUAL_BOT_JSON.exists():
        print(f"  [ERROR] Data files not found.")
        print(
            "  Make sure WRFrontiersDB-Data is cloned. "
            "Set DATA_REPO_PAT in .env and run:\n"
            "  git clone https://<PAT>@github.com/Surxe/WRFrontiersDB-Data.git WRFrontiersDB-Data"
        )
        sys.exit(1)

    game_data = []
    
    # 1. Process VirtualBots
    with open(VIRTUAL_BOT_JSON, encoding="utf-8") as f:
        virtual_bots = json.load(f)
        
    vbots_added = 0
    for bot_id, bot in virtual_bots.items():
        name_field = bot.get("name", {})
        english_name = name_field.get("en", "")
        icon_path = bot.get("icon_path", "")
        
        if english_name and icon_path:
            game_data.append({
                "id": f"OBJID_VirtualBot::{bot_id}",
                "name": english_name,
                "image_path": icon_path.lstrip("/")
            })
            vbots_added += 1

    # 2. Process Modules (with filtering)
    with open(MODULE_JSON, encoding="utf-8") as f:
        modules = json.load(f)

    ALLOWED_GROUPS = ["supply-gear", "cycle-gear", "light-weapon", "heavy-weapon", "titan-weapon"]
    modules_added = 0

    for module_id, module in modules.items():
        if module.get("production_status") != "Ready":
            continue

        # Check module_group_ref against allowed groups
        group_ref = module.get("module_group_ref", "")
        if not any(allowed in group_ref for allowed in ALLOWED_GROUPS):
            continue

        name_field = module.get("name", {})
        english_name = name_field.get("en", "")
        if not english_name:
            continue

        icon_path = module.get("inventory_icon_path", "")
        if not icon_path:
            continue

        game_data.append({
            "id": f"OBJID_Module::{module_id}",
            "name": english_name,
            "image_path": icon_path.lstrip("/")
        })
        modules_added += 1

    print(f"  -> {vbots_added} Virtual Bots and {modules_added} Modules found.")
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
