import sys
import json
import re
from pathlib import Path
from config import (
    DISCOUNTS_OUTPUT,
    MODULE_JSON,
    VIRTUAL_BOT_JSON,
    MODULE_TYPE_JSON,
    CHARACTER_PRESET_JSON,
    REPO_ROOT,
    FRONTEND_DATA_DIR,
    STANDALONE_MODULE_GROUPS,
    WEEKS_MANIFEST,
)
from week_dates import format_week, normalize_week, week_slug, week_sort_key
import grid_generator

def parse_ref(ref: str) -> tuple[str, str]:
    """
    Converts a reference like 'OBJID_VirtualBot::varangian' 
    to a tuple of (objtype, id), e.g., ('VirtualBot', 'varangian').
    """
    if "::" in ref:
        prefix, obj_id = ref.split("::", 1)
        obj_type = prefix.replace("OBJID_", "")
        return obj_type, obj_id
    return "", ref

def get_module_info(module_id: str, modules_data: dict) -> dict | None:
    """
    Extracts id and name from a Module dictionary.
    """
    module = modules_data.get(module_id)
    if not module:
        return None
    
    name_field = module.get("name", {})
    english_name = name_field.get("en", "")
    
    if english_name:
        return {
            "id": module_id,
            "name": english_name
        }
    return None

def load_discounts() -> list[dict]:
    """
    Reads the LLM-generated discounts.json output (which is a list of refs).
    Reconstitutes the full metadata by looking them up directly in Module.json and VirtualBot.json.
    For VirtualBot objtypes, expands to its core modules.
    Writes the result to a date-keyed JSON file in frontend public/data/
    and registers it in the weeks.json manifest.
    """
    print("[4/4] Reading LLM output from prompt/output/discounts.json...")

    if not DISCOUNTS_OUTPUT.exists():
        print(f"  [ERROR] Output file not found: {DISCOUNTS_OUTPUT}")
        print("  The Gemini CLI may not have written the output file.")
        sys.exit(1)

    with open(DISCOUNTS_OUTPUT, encoding="utf-8") as f:
        content = f.read().strip()

    # Locate the JSON object substring between the first '{' and last '}'
    first_brace = content.find('{')
    last_brace = content.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        content = content[first_brace:last_brace + 1]

    try:
        output_data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  [ERROR] Output is not valid JSON: {e}")
        print(f"  Content preview: {content[:300]}")
        sys.exit(1)

    if not isinstance(output_data, dict) or "items" not in output_data:
        print("  [ERROR] Output is not a JSON object containing 'items'.")
        sys.exit(1)


    try:
        week = normalize_week(output_data.get("week") or output_data)
    except ValueError:
        date_range = output_data.get("date_range", "")
        if not date_range:
            print("  [ERROR] Output week/date_range is empty or missing.")
            sys.exit(1)
        try:
            week = normalize_week(date_range)
        except ValueError as e:
            print(f"  [ERROR] Could not parse output date range: {e}")
            sys.exit(1)

    display_name = format_week(week, "long")

    discount_refs = output_data.get("items", [])
    if not isinstance(discount_refs, list):
        print("  [ERROR] 'items' must be a list.")
        sys.exit(1)

    for m_ref in discount_refs:
        if not isinstance(m_ref, str):
            print(f"  [ERROR] Invalid item format. Expected string, got {type(m_ref).__name__}: {m_ref}")
            sys.exit(1)
        if not (m_ref.startswith("OBJID_VirtualBot::") or m_ref.startswith("OBJID_Module::")):
            print(f"  [ERROR] Invalid item format. Expected string starting with 'OBJID_VirtualBot::' or 'OBJID_Module::', got: {m_ref}")
            sys.exit(1)

    print(f"  -> Found {len(discount_refs)} valid ID matches for week '{display_name}'.")

    # Load constant JSONs
    if not MODULE_JSON.exists() or not VIRTUAL_BOT_JSON.exists() or not MODULE_TYPE_JSON.exists() or not CHARACTER_PRESET_JSON.exists():
        print(f"  [ERROR] Database JSONs not found.")
        sys.exit(1)

    with open(MODULE_JSON, encoding="utf-8") as f:
        modules_data = json.load(f)

    with open(VIRTUAL_BOT_JSON, encoding="utf-8") as f:
        virtual_bots_data = json.load(f)

    with open(MODULE_TYPE_JSON, encoding="utf-8") as f:
        module_types_data = json.load(f)

    with open(CHARACTER_PRESET_JSON, encoding="utf-8") as f:
        presets_data = json.load(f)

    discounts = []
    for m_ref in discount_refs:
        if not isinstance(m_ref, str):
            continue
        
        obj_type, obj_id = parse_ref(m_ref)
        
        if obj_type == "VirtualBot":
            vbot = virtual_bots_data.get(obj_id)
            if vbot:
                print(f"     • Resolved VirtualBot: {obj_id}")
                # STANDALONE_MODULE_GROUPS are included as standalone items in step2;
                # exclude them here so built-in weapons (e.g. Norna's Coriolis)
                # are not listed as robot frame parts.
                for core_ref in vbot.get("core_module_refs", []):
                    c_type, c_id = parse_ref(core_ref)
                    module = modules_data.get(c_id)
                    if not module:
                        continue
                    group_ref = module.get("module_group_ref", "")
                    if any(group in group_ref for group in STANDALONE_MODULE_GROUPS):
                        print(f"       - Skipping weapon/gear core module: {c_id}")
                        continue
                    minfo = get_module_info(c_id, modules_data)
                    if minfo:
                        discounts.append(minfo)
                        print(f"       + Extracted Core Module: {minfo['name']}")
            else:
                print(f"     [!] Warning: VirtualBot ID {obj_id} not found.")

        elif obj_type == "Module":
            minfo = get_module_info(obj_id, modules_data)
            if minfo:
                discounts.append(minfo)
                print(f"     • Resolved Module: {minfo['name']} ({minfo['id']})")
            else:
                print(f"     [!] Warning: Module ID {obj_id} not found.")
        else:
            print(f"     [!] Warning: Unknown objtype {obj_type} in ref {m_ref}")

    # Write the full discounts data to archive directory
    archive_output_dir = REPO_ROOT / "archive" / "discounts"
    archive_output_dir.mkdir(parents=True, exist_ok=True)
    slug = week_slug(week)
    filename = f"discounts_{slug}.json"
    archive_output = archive_output_dir / filename
    
    frontend_data = {
        "week": week,
        "items": discounts
    }
    
    with open(archive_output, "w", encoding="utf-8") as f:
        json.dump(frontend_data, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote {len(discounts)} items to {archive_output.relative_to(REPO_ROOT)}")

    # Build and write grid layout data
    module_ids_for_grid = [item["id"] for item in discounts]
    grid_data = grid_generator.build_grid(
        module_ids_for_grid,
        modules_data,
        module_types_data,
        virtual_bots_data,
        presets_data
    )
    
    week_grids_dir = FRONTEND_DATA_DIR / "week_grids"
    week_grids_dir.mkdir(parents=True, exist_ok=True)
    grid_filename = f"grid_{slug}.json"
    grid_output = week_grids_dir / grid_filename
    with open(grid_output, "w", encoding="utf-8") as f:
        json.dump(grid_data, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote grid layout to {grid_output.relative_to(REPO_ROOT)}")
    
    # Write columns definitions
    columns_filename = "columns.json"
    columns_output = FRONTEND_DATA_DIR / columns_filename
    with open(columns_output, "w", encoding="utf-8") as f:
        json.dump(grid_generator.COL_HEADER_REPRESENTATIVES, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote columns definitions to {columns_output.relative_to(REPO_ROOT)}")

    # Update manifest weeks.json
    manifest_data = {"weeks": []}
    if WEEKS_MANIFEST.exists():
        try:
            with open(WEEKS_MANIFEST, encoding="utf-8") as f:
                manifest_data = json.load(f)
                if not isinstance(manifest_data, dict) or "weeks" not in manifest_data:
                    manifest_data = {"weeks": []}
        except Exception as e:
            print(f"  [!] Warning parsing weeks.json manifest: {e}. Recreating manifest.")

    grid_manifest_path = f"week_grids/grid_{slug}.json"

    # Remove existing entry if we are overwriting it
    manifest_data["weeks"] = [
        w for w in manifest_data["weeks"]
        if w.get("slug") != slug and w.get("file") != grid_manifest_path
    ]

    # Add the new week entry
    manifest_data["weeks"].append({
        "week": week,
        "file": grid_manifest_path,
        "slug": slug
    })

    # Sort descending (most recent first)
    manifest_data["weeks"].sort(key=week_sort_key, reverse=True)

    with open(WEEKS_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    print(f"  -> Updated manifest at {WEEKS_MANIFEST.relative_to(REPO_ROOT)}")

    return frontend_data

def run_step() -> list[dict]:
    return load_discounts()

if __name__ == "__main__":
    run_step()

