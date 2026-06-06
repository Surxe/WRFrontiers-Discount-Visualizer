"""
migrate_to_grids.py

Converts existing discounts_*.json files (flat expanded module lists) directly
into week_grids/*.json via grid_generator, then archives the originals.

The existing discounts_*.json files already contain the expanded {id, name} items
(step4 output format), so we skip step4's VirtualBot expansion and call
grid_generator.build_grid() directly with those module IDs.
"""

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
FRONTEND_DATA_DIR = REPO_ROOT / "src" / "frontend" / "public" / "data"
ARCHIVE_DIR = REPO_ROOT / "archive" / "discounts"
BACKEND_DIR = REPO_ROOT / "src" / "backend"
DATA_REPO_CANDIDATES = [
    REPO_ROOT / "WRFrontiersDB-Data",
    REPO_ROOT.parent / "WRFrontiersDB-Data",
]

sys.path.insert(0, str(BACKEND_DIR))
import grid_generator
from config import date_range_to_slug, WEEKS_MANIFEST

# Resolve data repo
data_repo = None
for candidate in DATA_REPO_CANDIDATES:
    if (candidate / "current" / "Objects" / "Module.json").exists():
        data_repo = candidate
        break

if not data_repo:
    print("[ERROR] Could not find WRFrontiersDB-Data repo.")
    sys.exit(1)

objects_dir = data_repo / "current" / "Objects"

def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

print("Loading database JSONs...")
modules_data = read_json(objects_dir / "Module.json")
module_types_data = read_json(objects_dir / "ModuleType.json")
virtual_bots_data = read_json(objects_dir / "VirtualBot.json")
presets_data = read_json(objects_dir / "CharacterPreset.json")
print(f"  Loaded {len(modules_data)} modules, {len(module_types_data)} module types, {len(virtual_bots_data)} vbots, {len(presets_data)} presets")
print()

discount_files = sorted(FRONTEND_DATA_DIR.glob("discounts_*.json"))

if not discount_files:
    print("No discounts_*.json files found in frontend/public/data/. Nothing to migrate.")
    sys.exit(0)

print(f"Found {len(discount_files)} discount file(s) to migrate:")
for f in discount_files:
    print(f"  - {f.name}")
print()

week_grids_dir = FRONTEND_DATA_DIR / "week_grids"
week_grids_dir.mkdir(parents=True, exist_ok=True)

# Load manifest
manifest_data = {"weeks": []}
if WEEKS_MANIFEST.exists():
    try:
        manifest_data = read_json(WEEKS_MANIFEST)
        if not isinstance(manifest_data, dict) or "weeks" not in manifest_data:
            manifest_data = {"weeks": []}
    except Exception as e:
        print(f"  [!] Warning parsing weeks.json: {e}. Recreating manifest.")

import re

def get_sort_key(week_entry):
    dr = week_entry.get("date_range", "")
    months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
    match = re.match(r'([A-Za-z]+)\s+(\d+)', dr)
    if match:
        m_name, d_val = match.groups()
        try:
            return (months.index(m_name.lower()[:3]), int(d_val))
        except ValueError:
            pass
    return (99, 99)

failed = []

for discount_file in discount_files:
    print(f"{'='*60}")
    print(f"Processing: {discount_file.name}")

    data = read_json(discount_file)
    date_range = data.get("date_range", "")
    items = data.get("items", [])

    if not date_range:
        print(f"  [ERROR] No date_range found, skipping.")
        failed.append(discount_file.name)
        continue

    module_ids = [item["id"] for item in items if item.get("id")]
    print(f"  -> {len(module_ids)} module IDs to process for '{date_range}'")

    grid_data = grid_generator.build_grid(
        module_ids,
        modules_data,
        module_types_data,
        virtual_bots_data,
        presets_data
    )

    slug = date_range_to_slug(date_range)
    grid_filename = f"grid_{slug}.json"
    grid_output = week_grids_dir / grid_filename

    with open(grid_output, "w", encoding="utf-8") as f:
        json.dump(grid_data, f, indent=2, ensure_ascii=False)

    std = len(grid_data.get("standardRows", []))
    titan = len(grid_data.get("titanRows", []))
    print(f"  -> Wrote {std} standard row(s), {titan} titan row(s) to week_grids/{grid_filename}")

    # Update manifest
    grid_manifest_path = f"week_grids/{grid_filename}"
    manifest_data["weeks"] = [
        w for w in manifest_data["weeks"]
        if w.get("date_range") != date_range and w.get("file") != grid_manifest_path
    ]
    manifest_data["weeks"].append({
        "date_range": date_range,
        "file": grid_manifest_path,
        "slug": slug
    })
    print(f"  -> Updated manifest entry for '{date_range}'")
    print()

# Sort manifest descending
manifest_data["weeks"].sort(key=get_sort_key, reverse=True)
with open(WEEKS_MANIFEST, "w", encoding="utf-8") as f:
    json.dump(manifest_data, f, indent=2, ensure_ascii=False)
print(f"Wrote updated weeks.json with {len(manifest_data['weeks'])} entries.")
print()

# Write columns.json
columns_output = FRONTEND_DATA_DIR / "columns.json"
with open(columns_output, "w", encoding="utf-8") as f:
    json.dump(grid_generator.COL_HEADER_REPRESENTATIVES, f, indent=2, ensure_ascii=False)
print(f"Wrote columns.json.")
print()

# Archive originals
print(f"{'='*60}")
print(f"Archiving original discounts_*.json files to archive/discounts/...")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

for discount_file in discount_files:
    if discount_file.name in failed:
        print(f"  [SKIP] {discount_file.name} (failed, not archived)")
        continue
    dest = ARCHIVE_DIR / discount_file.name
    shutil.move(str(discount_file), str(dest))
    print(f"  Moved {discount_file.name} -> archive/discounts/")

print()
if failed:
    print(f"[WARNING] {len(failed)} file(s) failed:")
    for name in failed:
        print(f"  - {name}")
    sys.exit(1)
else:
    print("Migration complete!")
