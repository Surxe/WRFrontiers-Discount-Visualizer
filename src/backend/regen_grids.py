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
    date_range_to_slug,
)
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
        date_range = data.get("date_range", "")
        if not date_range:
            print(f"  [SKIP] {f.name}: no date_range")
            continue

        module_ids = [item["id"] for item in data.get("items", []) if item.get("id")]
        grid_data = grid_generator.build_grid(
            module_ids, modules_data, module_types_data, virtual_bots_data, presets_data
        )

        slug = date_range_to_slug(date_range)
        out = WEEK_GRIDS_DIR / f"grid_{slug}.json"
        json.dump(grid_data, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

        std = len(grid_data.get("standardRows", []))
        titan = len(grid_data.get("titanRows", []))
        print(f"  {slug}: {std} standard row(s), {titan} titan row(s) -> {out.name}")
        
        manifest_entries.append({
            "date_range": date_range,
            "file": f"week_grids/{out.name}",
            "slug": slug
        })

    def get_sort_key(week_entry):
        dr = week_entry.get("date_range", "")
        months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        import re
        match = re.search(r'([A-Za-z]+)\s+(\d+)(?:,?\s*(\d{4}))?', dr)
        if match:
            m_name, d_val, y_val = match.groups()
            try:
                m_idx = months.index(m_name.lower()[:3])
                year = int(y_val) if y_val else 0
                return (year, m_idx, int(d_val))
            except ValueError:
                pass
        return (0, 0, 0)
        
    manifest_entries.sort(key=get_sort_key, reverse=True)
    with open(FRONTEND_DATA_DIR / "weeks.json", "w", encoding="utf-8") as f:
        json.dump({"weeks": manifest_entries}, f, indent=2, ensure_ascii=False)
    print(f"  -> Rebuilt weeks.json manifest")

    print()
    print(f"Done. Regenerated {len(discount_files)} grid(s).")


if __name__ == "__main__":
    run()
