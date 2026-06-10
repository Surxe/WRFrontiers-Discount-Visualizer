"""Build reverse lookup data from archived discount weeks."""

import json
from pathlib import Path

from config import REVERSE_LOOKUP_OUTPUT, REPO_ROOT, STANDALONE_MODULE_GROUPS
from week_dates import normalize_week, week_slug


def build_reverse_lookup(archive_output_dir: Path, modules_data: dict):
    """Build reverse lookup data for virtual bots and allowed standalone modules."""
    print("[4/4] Building reverse lookup data from archive...")

    vbot_history = {}
    module_history = {}

    archive_files = sorted(archive_output_dir.glob("discounts_*.json"))
    for archive_file in archive_files:
        with open(archive_file, encoding="utf-8") as f:
            try:
                archive_data = json.load(f)
            except json.JSONDecodeError:
                print(f"  [WARN] Skipping invalid archive file: {archive_file}")
                continue

        week_value = archive_data.get("week")
        if not week_value:
            continue

        try:
            normalized_week = normalize_week(week_value)
            week_slug_value = week_slug(normalized_week)
        except Exception:
            continue

        items = archive_data.get("items", [])
        if not isinstance(items, list):
            continue

        for item_ref in items:
            if not isinstance(item_ref, str) or "::" not in item_ref:
                continue

            item_type, item_id = item_ref.split("::", 1)
            if item_type == "OBJID_VirtualBot":
                vbot_history.setdefault(item_ref, []).append(week_slug_value)
            elif item_type == "OBJID_Module":
                module = modules_data.get(item_id)
                if not module:
                    continue
                group_ref = module.get("module_group_ref", "")
                if not any(allowed in group_ref for allowed in STANDALONE_MODULE_GROUPS):
                    continue
                module_history.setdefault(item_ref, []).append(week_slug_value)

    for history in (vbot_history, module_history):
        for ref, weeks in history.items():
            history[ref] = sorted(set(weeks), reverse=True)

    reverse_lookup = {
        "virtualBots": vbot_history,
        "modules": module_history,
    }

    with open(REVERSE_LOOKUP_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(reverse_lookup, f, indent=2, ensure_ascii=False)

    print(f"  -> Wrote reverse lookup to {REVERSE_LOOKUP_OUTPUT.relative_to(REPO_ROOT)}")
