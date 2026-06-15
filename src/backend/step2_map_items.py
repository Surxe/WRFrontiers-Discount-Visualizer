"""
step2_map_items.py

Step 2: Take comma-separated items and a date range. Map the items using fuzzy matching
against game_data.json and manual_mapping.json. Expand VirtualBot refs to core_module_refs.
Outputs the final item list to discounts.json.
"""

import sys
import json
import difflib
from datetime import datetime
from config import TEMP_DIR, MANUAL_MAPPING_JSON, GAME_DATA_JSON, DISCOUNTS_OUTPUT, VIRTUAL_BOT_JSON, MODULE_JSON

def parse_date_range(date_str: str) -> dict:
    parts = date_str.split(" ")
    if len(parts) != 2:
        raise ValueError(f"Date range must be in format 'yyyy-mm-dd yyyy-mm-dd', got '{date_str}'")
    
    try:
        start_date = datetime.strptime(parts[0], "%Y-%m-%d")
        end_date = datetime.strptime(parts[1], "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format. Expected 'yyyy-mm-dd yyyy-mm-dd': {e}")
    
    return {
        "start_month": start_date.strftime("%B"),
        "start_day": start_date.day,
        "end_month": end_date.strftime("%B"),
        "end_day": end_date.day
    }

def map_items(items_str: str, date_range_str: str):
    print("[2/4] Mapping items using local fuzzy match...")

    # 1. Parse dates
    week_data = parse_date_range(date_range_str)

    # 2. Parse items
    raw_items = [i.strip() for i in items_str.split(",") if i.strip()]
    if not raw_items:
        print("  [ERROR] Item list is empty.")
        sys.exit(1)

    items = []
    seen = set()
    duplicates = set()
    for item in raw_items:
        lower_item = item.lower()
        if lower_item in seen:
            duplicates.add(item)
        else:
            seen.add(lower_item)
            items.append(item)
            
    if duplicates:
        print(f"  [ERROR] Duplicate items found: {', '.join(duplicates)}")
        sys.exit(1)

    # 3. Load data
    if not GAME_DATA_JSON.exists():
        print(f"  [ERROR] {GAME_DATA_JSON.name} not found. Run step 1 first.")
        sys.exit(1)

    with open(GAME_DATA_JSON, "r", encoding="utf-8") as f:
        game_data = json.load(f)

    manual_mapping = {}
    if MANUAL_MAPPING_JSON.exists():
        try:
            with open(MANUAL_MAPPING_JSON, "r", encoding="utf-8") as f:
                manual_mapping = json.load(f)
        except json.JSONDecodeError:
            print("  [WARNING] Could not decode manual_mapping.json. Starting fresh.")

    # Create lookups for game data
    name_to_ref = {entry["name"].lower(): entry["ref"] for entry in game_data}
    game_names_lower = list(name_to_ref.keys())
    game_name_lookup = {entry["name"].lower(): entry["name"] for entry in game_data}

    mapped_refs = []
    unmapped_items = []
    new_mappings_found = False

    # 4. Map each item
    for item in items:
        item_lower = item.lower()

        # Check manual mapping first
        if item in manual_mapping:
            mapped_refs.append(manual_mapping[item])
            continue
        if item_lower in manual_mapping:
            mapped_refs.append(manual_mapping[item_lower])
            continue

        # Check exact match
        if item_lower in name_to_ref:
            mapped_refs.append(name_to_ref[item_lower])
            continue

        # Fuzzy matching
        matches = difflib.get_close_matches(item_lower, game_names_lower, n=1, cutoff=0.5)
        if matches:
            best_match_lower = matches[0]
            best_ref = name_to_ref[best_match_lower]
            mapped_refs.append(best_ref)
            
            # Record non-1:1 match
            manual_mapping[item] = best_ref
            new_mappings_found = True
        else:
            unmapped_items.append(item)

    if unmapped_items:
        print(f"  [ERROR] Unable to map the following items: {unmapped_items}")
        sys.exit(1)

    if new_mappings_found:
        with open(MANUAL_MAPPING_JSON, "w", encoding="utf-8") as f:
            json.dump(manual_mapping, f, indent=2, ensure_ascii=False)
        print("  -> Updated manual_mapping.json with new fuzzy matches.")

    # 5. Expand Virtual Bots
    final_refs = []
    
    with open(VIRTUAL_BOT_JSON, "r", encoding="utf-8") as f:
        virtual_bots = json.load(f)
        
    with open(MODULE_JSON, "r", encoding="utf-8") as f:
        modules = json.load(f)
        
    for ref in mapped_refs:
        if ref.startswith("OBJID_VirtualBot::"):
            bot_id = ref.split("::", 1)[1]
            if bot_id in virtual_bots:
                core_refs = virtual_bots[bot_id].get("core_module_refs", [])
                # Filter out titan weapons
                for core_ref in core_refs:
                    if core_ref.startswith("OBJID_Module::"):
                        mod_id = core_ref.split("::", 1)[1]
                        mod_data = modules.get(mod_id, {})
                        if mod_data.get("module_group_ref") == "OBJID_ModuleGroup::titan-weapon":
                            continue
                    final_refs.append(core_ref)
            else:
                print(f"  [WARNING] VirtualBot {bot_id} not found in VirtualBot.json")
                final_refs.append(ref)
        else:
            final_refs.append(ref)

    # 6. Save output
    output_data = {
        "week": week_data,
        "items": final_refs
    }

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    DISCOUNTS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(DISCOUNTS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"  -> Successfully mapped {len(items)} items to {len(final_refs)} refs.")
    print(f"  -> Output saved to {DISCOUNTS_OUTPUT.name}")

def run_step(items_str: str, date_range_str: str):
    map_items(items_str, date_range_str)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python step2_map_items.py \"Item1, Item2\" \"yyyy-mm-dd yyyy-mm-dd\"")
        sys.exit(1)
    
    run_step(sys.argv[1], sys.argv[2])
