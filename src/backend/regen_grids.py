"""
regen_grids.py

Regenerates all week_grids/*.json files from archive/discounts/*.json
by passing them through grid_generator.build_grid().

When to run: after any bug fix to grid_generator.py, to retroactively
apply the corrected layout logic to all archived historical weeks.

Usage:
    python src/backend/regen_grids.py
"""

import json
import sys
from pathlib import Path

from config import (
    REPO_ROOT,
    FRONTEND_DATA_DIR,
    MODULE_JSON,
    VIRTUAL_BOT_JSON,
    MODULE_TYPE_JSON,
    CHARACTER_PRESET_JSON,
)
from week_dates import format_week, normalize_week, week_slug, week_sort_key
import grid_generator

ARCHIVE_DIR = REPO_ROOT / "archive" / "discounts"
WEEK_GRIDS_DIR = FRONTEND_DATA_DIR / "week_grids"


def run():
    if not ARCHIVE_DIR.exists():
        print(f"[ERROR] Archive directory not found: {ARCHIVE_DIR}")
        sys.exit(1)

    discount_files = sorted(ARCHIVE_DIR.glob("discounts_*.json"))
    if not discount_files:
        print("No discounts_*.json files found in archive/discounts/. Nothing to regenerate.")
        sys.exit(0)

    print(f"Loading database JSONs...")
    modules_data = json.load(open(MODULE_JSON, encoding="utf-8"))
    module_types_data = json.load(open(MODULE_TYPE_JSON, encoding="utf-8"))
    virtual_bots_data = json.load(open(VIRTUAL_BOT_JSON, encoding="utf-8"))
    presets_data = json.load(open(CHARACTER_PRESET_JSON, encoding="utf-8"))
    print(f"  Loaded {len(modules_data)} modules, {len(module_types_data)} module types, "
          f"{len(virtual_bots_data)} vbots, {len(presets_data)} presets")
    print()

    WEEK_GRIDS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []

    for f in discount_files:
        data = json.load(open(f, encoding="utf-8"))
        try:
            week = normalize_week(data.get("week") or data)
        except ValueError:
            date_range = data.get("date_range", "")
            if not date_range:
                print(f"  [SKIP] {f.name}: no week/date_range")
                continue
            week = normalize_week(date_range)
        if not week:
            continue

        module_ids = [item["id"] for item in data.get("items", []) if item.get("id")]
        grid_data = grid_generator.build_grid(
            module_ids, modules_data, module_types_data, virtual_bots_data, presets_data
        )

        slug = week_slug(week)
        out = WEEK_GRIDS_DIR / f"grid_{slug}.json"
        json.dump(grid_data, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

        std = len(grid_data.get("standardRows", []))
        titan = len(grid_data.get("titanRows", []))
        print(f"  {slug}: {format_week(week, 'long')} - {std} standard row(s), {titan} titan row(s) -> {out.name}")
        
        manifest_entries.append({
            "week": week,
            "file": f"week_grids/{out.name}",
            "slug": slug
        })

    manifest_entries.sort(key=week_sort_key, reverse=True)
    with open(FRONTEND_DATA_DIR / "weeks.json", "w", encoding="utf-8") as f:
        json.dump({"weeks": manifest_entries}, f, indent=2, ensure_ascii=False)
    print(f"  -> Rebuilt weeks.json manifest")

    print()
    print(f"Done. Regenerated {len(discount_files)} grid(s).")


if __name__ == "__main__":
    run()
