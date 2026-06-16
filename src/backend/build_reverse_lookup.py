"""Build reverse lookup data from archived discount weeks."""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from config import (
    REVERSE_LOOKUP_OUTPUT,
    REPO_ROOT,
    STANDALONE_MODULE_GROUPS,
    VIRTUAL_BOT_JSON,
    MODULE_JSON,
    CHARACTER_PRESET_JSON,
)
from week_dates import normalize_week, week_slug


def parse_ref(ref: str) -> tuple[str, str]:
    """Parse a reference string into type and ID."""
    if not isinstance(ref, str):
        return "", ""
    if "::" in ref:
        prefix, obj_id = ref.split("::", 1)
        obj_type = prefix.replace("OBJID_", "")
        return obj_type, obj_id
    return "", ref


def calculate_avg_weeks_between_discounts(weeks: list[str]) -> float | None:
    """Calculate the average number of weeks between discounts.
    
    Expects a list of week slugs (YYYY-MM-DD) sorted in reverse chronological order.
    Disregards time since the last discount. Returns None if there are fewer than 2 discounts.
    """
    if not weeks or len(weeks) < 2:
        return None
        
    oldest_week = weeks[-1]
    newest_week = weeks[0]
    
    try:
        oldest_date = datetime.strptime(oldest_week, "%Y-%m-%d")
        newest_date = datetime.strptime(newest_week, "%Y-%m-%d")
    except ValueError:
        return None
        
    days_diff = (newest_date - oldest_date).days
    weeks_diff = days_diff / 7.0
    
    # The number of intervals is the number of discounts - 1
    average_weeks = weeks_diff / (len(weeks) - 1)
    return round(average_weeks, 1)


def is_body_part_module(module_id: str) -> bool:
    """Check if a module is a chassis, torso, or shoulder module based on its ID."""
    lower_id = module_id.lower()
    return (
        "chassis" in lower_id or
        "torso" in lower_id or
        "shoulder" in lower_id
    )


def build_reverse_lookup(archive_output_dir: Path):
    """Build reverse lookup data for virtual bots and allowed standalone modules."""
    print("  -> Building reverse lookup data from archive...")

    vbot_history = {}
    module_history = {}

    # Load module data to identify body part modules and build module-to-vbot mapping
    modules_data = {}
    if MODULE_JSON.exists():
        with open(MODULE_JSON, encoding="utf-8") as f:
            modules_data = json.load(f)
    else:
        print(f"  [WARN] Module.json not found at {MODULE_JSON}")

    # Load virtual bot data
    vbot_data = {}
    if VIRTUAL_BOT_JSON.exists():
        with open(VIRTUAL_BOT_JSON, encoding="utf-8") as f:
            vbot_data = json.load(f)
    else:
        print(f"  [WARN] VirtualBot.json not found at {VIRTUAL_BOT_JSON}")

    # Build module -> vbot mapping for body parts (chassis/torso/shoulder only)
    module_to_vbot = {}
    for vbot_id, vbot_info in vbot_data.items():
        for module_ref in vbot_info.get("core_module_refs", []):
            _, module_id = parse_ref(module_ref)
            if module_id and is_body_part_module(module_id):
                module_to_vbot[module_id] = vbot_id

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

        for item_id in items:
            if not isinstance(item_id, str):
                continue

            # Handle both old format (OBJID::) and new format (just ID)
            if "::" in item_id:
                # Old format with OBJID prefix
                item_type, actual_id = item_id.split("::", 1)
                if item_type == "OBJID_VirtualBot":
                    vbot_history.setdefault(item_id, []).append(week_slug_value)
                elif item_type == "OBJID_Module":
                    module_history.setdefault(item_id, []).append(week_slug_value)
                    # If it's a body part module (chassis/torso/shoulder), add to vbot history
                    if is_body_part_module(actual_id) and actual_id in module_to_vbot:
                        vbot_id = module_to_vbot[actual_id]
                        vbot_ref = f"OBJID_VirtualBot::{vbot_id}"
                        vbot_history.setdefault(vbot_ref, []).append(week_slug_value)
            else:
                # New format without OBJID prefix
                # Determine if item is a module or vbot based on ID format
                # Modules start with "DA_Module_", vbots are simple names
                if item_id.startswith("DA_Module_"):
                    # It's a module
                    module_ref = f"OBJID_Module::{item_id}"
                    module_history.setdefault(module_ref, []).append(week_slug_value)
                    # If it's a body part module (chassis/torso/shoulder), add to vbot history
                    if is_body_part_module(item_id) and item_id in module_to_vbot:
                        vbot_id = module_to_vbot[item_id]
                        vbot_ref = f"OBJID_VirtualBot::{vbot_id}"
                        vbot_history.setdefault(vbot_ref, []).append(week_slug_value)
                else:
                    # It's a vbot
                    vbot_ref = f"OBJID_VirtualBot::{item_id}"
                    vbot_history.setdefault(vbot_ref, []).append(week_slug_value)

    for history in (vbot_history, module_history):
        for ref, weeks in history.items():
            history[ref] = sorted(set(weeks), reverse=True)

    # Build module-to-vbot mapping for standalone module categories
    module_to_vbots = defaultdict(set)

    # Load character preset data for factory preset modules
    character_preset_data = {}
    if CHARACTER_PRESET_JSON.exists():
        with open(CHARACTER_PRESET_JSON, encoding="utf-8") as f:
            character_preset_data = json.load(f)
    else:
        print(f"  [WARN] CharacterPreset.json not found at {CHARACTER_PRESET_JSON}")

    # Build module to vbot mapping from core_module_refs and factory presets
    for vbot_id, vbot_info in vbot_data.items():
        if not vbot_info:
            continue

        # Get core module refs
        core_module_refs = vbot_info.get("core_module_refs", [])
        if isinstance(core_module_refs, str):
            core_module_refs = [core_module_refs]

        for module_ref in core_module_refs:
            _, module_id = parse_ref(module_ref)
            if module_id:
                module_to_vbots[module_id].add(vbot_id)

        # Also check factory presets for additional module relationships
        factory_preset_refs = vbot_info.get("factory_preset_refs", [])
        if isinstance(factory_preset_refs, str):
            factory_preset_refs = [factory_preset_refs]

        for preset_ref in factory_preset_refs:
            _, preset_id = parse_ref(preset_ref)
            preset_data = character_preset_data.get(preset_id, {})
            preset_modules = preset_data.get("modules", [])

            for module_data in preset_modules:
                module_ref = module_data.get("module_ref", "")
                _, module_id = parse_ref(module_ref)
                if module_id:
                    module_to_vbots[module_id].add(vbot_id)

    # Convert sets to sorted lists for consistent output
    module_to_vbots = {k: sorted(list(v)) for k, v in module_to_vbots.items()}

    # Build enhanced module data with vbot relationships
    enhanced_module_history = {}

    for module_ref, weeks in module_history.items():
        _, module_id = parse_ref(module_ref)

        # Get module group to determine if it's a standalone module category
        module_info = modules_data.get(module_id, {})
        module_group_ref = module_info.get("module_group_ref", "")
        _, module_group_id = parse_ref(module_group_ref)

        # Only add vbot relationships for standalone module categories
        virtual_bots = []
        if module_group_id in STANDALONE_MODULE_GROUPS:
            virtual_bots = module_to_vbots.get(module_id, [])

        enhanced_module_history[module_ref] = {
            "weeks": weeks,
            "virtual_bots": virtual_bots,
            "avg_weeks_between_discounts": calculate_avg_weeks_between_discounts(weeks)
        }

    # Build enhanced vbot data (keeping existing structure for consistency)
    enhanced_vbot_history = {}
    for vbot_ref, weeks in vbot_history.items():
        enhanced_vbot_history[vbot_ref] = {
            "weeks": weeks,
            "avg_weeks_between_discounts": calculate_avg_weeks_between_discounts(weeks)
        }

    reverse_lookup = {
        "virtualBots": enhanced_vbot_history,
        "modules": enhanced_module_history,
    }

    with open(REVERSE_LOOKUP_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(reverse_lookup, f, indent=2, ensure_ascii=False)

    print(f"  -> Wrote reverse lookup to {REVERSE_LOOKUP_OUTPUT.relative_to(REPO_ROOT)}")
