import sys
import json
from pathlib import Path
from config import (
    DISCOUNTS_OUTPUT,
    MODULE_JSON,
    VIRTUAL_BOT_JSON,
    MODULE_TYPE_JSON,
    CHARACTER_PRESET_JSON,
    REPO_ROOT,
    FRONTEND_DATA_DIR,
    WEEKS_MANIFEST,    REVERSE_LOOKUP_OUTPUT,
    STANDALONE_MODULE_GROUPS,)
from week_dates import format_week, normalize_week, week_slug, week_sort_key
import grid_generator
from build_reverse_lookup import build_reverse_lookup

def process_discount():
    """
    Reads the LLM-generated discounts.json output (which is a list of refs).
    Writes the result to a date-keyed JSON file in archive/discounts/
    and generates the grid layout for that week.
    Updates the weeks.json manifest.
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

    week = output_data.get("week")
    if not week:
        print("  [ERROR] Output 'week' field is missing.")
        sys.exit(1)

    try:
        week = normalize_week(week)
    except (ValueError, TypeError) as e:
        print(f"  [ERROR] Could not parse week: {e}")
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

    print(f"  -> Found {len(discount_refs)} items for week '{display_name}'.")

    # Load database JSONs for grid generation
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

    # Write the discounts data to archive directory (just the list of IDs)
    archive_output_dir = REPO_ROOT / "archive" / "discounts"
    archive_output_dir.mkdir(parents=True, exist_ok=True)
    slug = week_slug(week)
    filename = f"discounts_{slug}.json"
    archive_output = archive_output_dir / filename
    
    # Strip OBJID prefix from refs for archive format
    archive_items = []
    for ref in discount_refs:
        if "::" in ref:
            _, item_id = ref.split("::", 1)
            archive_items.append(item_id)
        else:
            archive_items.append(ref)
    
    archive_data = {
        "week": week,
        "items": archive_items
    }
    
    with open(archive_output, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote {len(archive_items)} items to {archive_output.relative_to(REPO_ROOT)}")

    # Build and write grid layout data
    grid_data = grid_generator.build_grid(
        discount_refs,
        modules_data,
        module_types_data,
        virtual_bots_data,
        presets_data
    )
    
    week_grids_dir = FRONTEND_DATA_DIR / "week_grids"
    week_grids_dir.mkdir(parents=True, exist_ok=True)
    grid_filename = f"grid_{slug}.json"
    grid_output = week_grids_dir / grid_filename
    
    # Add week data to grid output for frontend consumption
    grid_data_with_week = {
        "week": week,
        "grid": grid_data
    }

    with open(grid_output, "w", encoding="utf-8") as f:
        json.dump(grid_data_with_week, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote grid layout to {grid_output.relative_to(REPO_ROOT)}")
    
    # Write columns definitions
    columns_filename = "columns.json"
    columns_output = FRONTEND_DATA_DIR / columns_filename
    with open(columns_output, "w", encoding="utf-8") as f:
        json.dump(grid_generator.COL_HEADER_REPRESENTATIVES, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote columns definitions to {columns_output.relative_to(REPO_ROOT)}")

    build_reverse_lookup(archive_output_dir)

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

    # Sort descending (most recent first), using each entry's week value.
    manifest_data["weeks"].sort(
        key=lambda entry: week_sort_key(entry["week"]),
        reverse=True,
    )

    with open(WEEKS_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    print(f"  -> Updated manifest at {WEEKS_MANIFEST.relative_to(REPO_ROOT)}")

    return archive_data


def run_step():
    return process_discount()

if __name__ == "__main__":
    run_step()
