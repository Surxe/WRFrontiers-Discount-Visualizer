"""
step2_map_items.py

Step 2: Take comma-separated items and a date range. Map each announced name to a
game_data ref, then expand VirtualBot refs to core_module_refs and write discounts.json.

Resolution order per item:
  1. manual_mapping.json  -- exact override/pin (value may be a single ref or a list
     of refs, for a known mis-split like "Ceresm Norna" -> [Ceres, Norna]).
  2. exact vocab name match against game_data.json.
  3. Jev  -- TypeSafe AI's typed closed-set classifier (see jev_mapper.py). Used when
     a JEV_API_KEY is configured; resolves typos / plurals / mis-splits and records
     each new hit back into manual_mapping.json for a deterministic, reviewable rerun.
  4. difflib fuzzy match  -- OFFLINE FALLBACK ONLY, when no Jev key is configured, so
     tests and keyless local runs still work.

With Jev configured, a name it cannot resolve confidently is raised as an error
(listing Jev's best guess + confidence) rather than silently fuzzy-matched, so a
genuinely new/unknown item surfaces for a human to map.
"""

import sys
import json
import difflib
from datetime import datetime
from config import (
    TEMP_DIR, MANUAL_MAPPING_JSON, GAME_DATA_JSON, DISCOUNTS_OUTPUT,
    VIRTUAL_BOT_JSON, MODULE_JSON,
    JEV_API_KEY, JEV_MODEL, JEV_ACCEPT_THRESHOLD, JEV_SPLIT_PIECE_THRESHOLD,
)
from jev_mapper import JevMapper

def parse_date_range(date_str: str) -> dict:
    parts = date_str.split(" ")
    if len(parts) != 2:
        raise ValueError(f"Date range must be in format 'mm-dd mm-dd', got '{date_str}'")
    
    current_year = datetime.now().year
    
    try:
        start_date = datetime.strptime(f"{current_year}-{parts[0]}", "%Y-%m-%d")
        
        end_month_str, end_day_str = parts[1].split("-")
        end_month = int(end_month_str)
        end_year = current_year
        if end_month < start_date.month:
            end_year += 1
            
        end_date = datetime.strptime(f"{end_year}-{parts[1]}", "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format. Expected 'mm-dd mm-dd': {e}")
    
    return {
        "start_month": start_date.strftime("%B"),
        "start_day": start_date.day,
        "end_month": end_date.strftime("%B"),
        "end_day": end_date.day
    }

def perform_mapping(
    items: list[str],
    game_data: list[dict],
    manual_mapping: dict,
    mapper: JevMapper | None = None,
) -> tuple[list[str], dict, bool]:
    """
    Map a list of announced names to game_data refs (see module docstring for order).

    Args:
        mapper: a JevMapper. If None or not available (no key), Jev is skipped and
                unresolved names fall back to difflib fuzzy matching (offline mode).
    Returns:
        (mapped_refs, updated_manual_mapping, new_mappings_found)
    Raises:
        ValueError: If any items cannot be mapped.
    """
    name_to_ref = {entry["name"].lower(): entry["ref"] for entry in game_data}
    game_names_lower = list(name_to_ref.keys())
    criteria = {entry["ref"]: entry["name"] for entry in game_data}
    use_jev = mapper is not None and mapper.available

    mapped_refs = []
    unmapped_items = []
    updated_manual_mapping = dict(manual_mapping)
    new_mappings_found = False

    for item in items:
        item_lower = item.lower()

        # 1. Manual mapping (exact then lowercased). Value may be a ref or a list.
        manual_val = updated_manual_mapping.get(item)
        if manual_val is None:
            manual_val = updated_manual_mapping.get(item_lower)
        if manual_val is not None:
            mapped_refs.extend(manual_val if isinstance(manual_val, list) else [manual_val])
            continue

        # 2. Exact vocab name match.
        if item_lower in name_to_ref:
            mapped_refs.append(name_to_ref[item_lower])
            continue

        # 3. Jev (typed closed-set classifier), when configured.
        if use_jev:
            res = mapper.resolve(item, criteria)
            if res.ok:
                mapped_refs.extend(res.refs)
                # Record so a rerun is deterministic and the hit is reviewable in git.
                updated_manual_mapping[item] = res.refs if len(res.refs) > 1 else res.refs[0]
                new_mappings_found = True
                names = ", ".join(criteria.get(r, r) for r in res.refs)
                print(f"  [jev] {item!r} -> {names} ({res.method}, conf={res.confidence:.2f})")
            else:
                best = criteria.get(res.detail.get("best"), res.detail.get("best"))
                unmapped_items.append(f"{item} (jev best: {best} @ {res.confidence:.2f})")
            continue

        # 4. Offline fallback: difflib fuzzy match (only when Jev is unavailable).
        matches = difflib.get_close_matches(item_lower, game_names_lower, n=1, cutoff=0.5)
        if matches:
            best_ref = name_to_ref[matches[0]]
            mapped_refs.append(best_ref)
            updated_manual_mapping[item] = best_ref
            new_mappings_found = True
        else:
            unmapped_items.append(item)

    if unmapped_items:
        raise ValueError(f"Unable to map the following items: {unmapped_items}")

    return mapped_refs, updated_manual_mapping, new_mappings_found


def map_items(items_str: str, date_range_str: str):
    mapper = JevMapper(
        api_key=JEV_API_KEY,
        model=JEV_MODEL,
        accept_threshold=JEV_ACCEPT_THRESHOLD,
        split_piece_threshold=JEV_SPLIT_PIECE_THRESHOLD,
    )
    engine = "Jev typed classifier" if mapper.available else "local fuzzy match (offline; no JEV_API_KEY)"
    print(f"[2/3] Mapping items using {engine}...")

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

    # 4. Map each item using perform_mapping
    try:
        mapped_refs, manual_mapping, new_mappings_found = perform_mapping(
            items, game_data, manual_mapping, mapper=mapper
        )
    except ValueError as e:
        print(f"  [ERROR] {e}")
        sys.exit(1)
    finally:
        mapper.close()

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
