import json
import collections

COL_HEADER_REPRESENTATIVES = [
    "VirtualBots",
    "OBJID_ModuleSocketType::DA_ModuleSocketType_Torso.0",
    "OBJID_ModuleSocketType::DA_ModuleSocketType_ShoulderL.0",
    "OBJID_ModuleCategory::DA_ModuleCategory_Chassis.0",
    "OBJID_ModuleSocketType::DA_ModuleSocketType_Weapon.0",
    "OBJID_ModuleSocketType::DA_ModuleSocketType_WeaponHeavy.0",
    "OBJID_ModuleSocketType::DA_ModuleSocketType_Ability3.0",
    "OBJID_ModuleSocketType::DA_ModuleSocketType_Ability4.0"
]

TITAN_SOCKET_MAP = {
    "titan-torsos": "DA_ModuleSocketType_Torso.0",
    "titan-chassis": "DA_ModuleCategory_Chassis.0",
    "titan-shoulder": "DA_ModuleSocketType_ShoulderL.0",
    "titan-weapon": "DA_ModuleSocketType_Weapon.0"
}

def parse_ref(ref: str) -> tuple[str, str]:
    if not isinstance(ref, str):
        return "", ""
    if "::" in ref:
        prefix, obj_id = ref.split("::", 1)
        obj_type = prefix.replace("OBJID_", "")
        return obj_type, obj_id
    return "", ref

def resolve_module_column(module, module_types_data: dict) -> int:
    module_type_ref = module.get("module_type_ref", "")
    module_group_ref = module.get("module_group_ref", "")
    
    _, module_type_id = parse_ref(module_type_ref)
    _, module_group_id = parse_ref(module_group_ref)

    module_type = module_types_data.get(module_type_id, {})
    character_type = module_type.get("character_type", "")
    
    socket = None
    if character_type == "Titan":
        socket = TITAN_SOCKET_MAP.get(module_group_id)
    else:
        socket_ref = module_type.get("exclusive_module_socket_type_ref", "")
        if socket_ref:
            _, socket = parse_ref(socket_ref)
        else:
            cat_ref = module_type.get("module_category_ref", "")
            if cat_ref:
                _, socket = parse_ref(cat_ref)
                
    # Search for the socket ID within the references in COL_HEADER_REPRESENTATIVES
    for idx, rep in enumerate(COL_HEADER_REPRESENTATIVES):
        if rep == "VirtualBots": continue
        _, rep_id = parse_ref(rep)
        if rep_id == socket:
            return idx + 1 # 1-based index
            
    return -1

def assign_items_to_bots(bots: list[dict], items: list[dict]) -> list:
    bot_ids = {b["vbot"] for b in bots}
    items_by_vbot = collections.defaultdict(list)
    unmatched_items = []
    
    for item in items:
        prefs = item.get("preferred_vbot", [])
        if isinstance(prefs, str):
            prefs = [prefs]
            
        has_preference = False
        for vbot in prefs:
            if "::" in vbot:
                _, vbot = parse_ref(vbot)
            if vbot in bot_ids:
                items_by_vbot[vbot].append(item)
                has_preference = True
                
        if not has_preference:
            unmatched_items.append(item)
            
    bot_items = []
    assigned_item_ids = set()
    
    for bot in bots:
        bot_id = bot["vbot"]
        preferred = items_by_vbot.get(bot_id, [])
        assigned = preferred[0] if preferred else None
        if assigned:
            assigned_item_ids.add(assigned["id"])
        bot_items.append(assigned)
        
    # Fill remaining slots with unmatched items
    unmatched_index = 0
    for i in range(len(bot_items)):
        if not bot_items[i] and unmatched_index < len(unmatched_items):
            bot_items[i] = unmatched_items[unmatched_index]
            assigned_item_ids.add(unmatched_items[unmatched_index]["id"])
            unmatched_index += 1
            
    unplaced = [i for i in items if i["id"] not in assigned_item_ids]
    target_length = max(len(bots), len(items))
    
    for w in unplaced:
        if len(bot_items) < target_length:
            bot_items.append(w)
            assigned_item_ids.add(w["id"])
        else:
            # Replace duplicate
            counts = collections.Counter(bw["id"] for bw in bot_items if bw)
            duplicates = [id for id, c in counts.items() if c > 1]
            if duplicates:
                dup_id = duplicates[0]
                # find last index of this dup
                last_idx = -1
                for i in range(len(bot_items)-1, -1, -1):
                    if bot_items[i] and bot_items[i]["id"] == dup_id:
                        last_idx = i
                        break
                bot_items[last_idx] = w
                assigned_item_ids.add(w["id"])
            else:
                bot_items.append(w) # just append if we can't replace
                assigned_item_ids.add(w["id"])
                
    return bot_items

def build_grid(module_ids: list[str], modules_data: dict, module_types_data: dict, virtual_bots_data: dict, presets_data: dict):
    # Build module-to-vbot mapping from factory presets
    module_to_vbot_map = collections.defaultdict(list)
    for vbot_id, vbot_data in virtual_bots_data.items():
        if not vbot_data:
            continue
        presets = vbot_data.get("factory_preset_refs", [])
        if isinstance(presets, str):
            presets = [presets]
        for preset_ref in presets:
            _, preset_id = parse_ref(preset_ref)
            preset = presets_data.get(preset_id)
            if preset and preset.get("modules"):
                for module_data in preset["modules"]:
                    module_ref = module_data.get("module_ref", "")
                    _, module_id = parse_ref(module_ref)
                    if module_id and vbot_id not in module_to_vbot_map[module_id]:
                        module_to_vbot_map[module_id].append(vbot_id)

    explicit_vbots_standard = []
    explicit_vbots_titan = []
    for module_ref in module_ids:
        prefix, obj_id = parse_ref(module_ref)
        if prefix == "VirtualBot" and obj_id:
            vbot_data = virtual_bots_data.get(obj_id, {})
            if vbot_data.get("character_type") == "Titan":
                if obj_id not in explicit_vbots_titan:
                    explicit_vbots_titan.append(obj_id)
            else:
                if obj_id not in explicit_vbots_standard:
                    explicit_vbots_standard.append(obj_id)

    # Enrich modules with grid info
    enriched_modules = []
    for module_ref in module_ids:
        _, mid = parse_ref(module_ref)
        if not mid:
            continue
        m = modules_data.get(mid)
        if not m:
            continue
        col = resolve_module_column(m, module_types_data)
        _, vbot = parse_ref(m.get("virtual_bot_ref", ""))
        
        mt = module_types_data.get(parse_ref(m.get("module_type_ref", ""))[1], {})
        is_titan = mt.get("character_type") == "Titan"
        
        preferred_vbot = module_to_vbot_map.get(mid, [])
        
        enriched_modules.append({
            "id": mid,
            "col": col,
            "vbot": vbot,
            "preferred_vbot": preferred_vbot,
            "is_titan": is_titan,
            "raw": m
        })
        
    standard_modules = [m for m in enriched_modules if not m["is_titan"]]
    titan_modules = [m for m in enriched_modules if m["is_titan"]]
    
    def process_items(items, is_titan=False):
        # group bots
        bot_parts = [i for i in items if i["col"] in (2, 3, 4)]
        bots_map = {}
        explicit_vbots_list = explicit_vbots_titan if is_titan else explicit_vbots_standard
        for vbot in explicit_vbots_list:
            bots_map[vbot] = {"vbot": vbot, 2: None, 3: None, 4: None}
        for part in bot_parts:
            vbot = part["vbot"] or part["id"]
            if vbot not in bots_map:
                bots_map[vbot] = {"vbot": vbot, 2: None, 3: None, 4: None}
            if not bots_map[vbot][part["col"]]:
                bots_map[vbot][part["col"]] = part["id"]
        
        bots = list(bots_map.values())
        
        # For titans, spill any second weapon preferred by the same bot into col 6
        # instead of letting it overflow to a new row.
        items_by_col = {5: [], 6: [], 7: [], 8: []}
        if is_titan:
            # Separate all titan-weapon items
            weapon_items = [i for i in items if i["col"] == 5]
            bot_ids = {b["vbot"] for b in bots}
            col5_used_bots = set()
            for item in weapon_items:
                prefs = item.get("preferred_vbot", [])
                if isinstance(prefs, str):
                    prefs = [prefs]
                matched_bot = next((v for v in prefs if v in bot_ids), None)
                if matched_bot and matched_bot not in col5_used_bots:
                    items_by_col[5].append(item)
                    col5_used_bots.add(matched_bot)
                else:
                    # Overflow second+ weapon for same bot to col 6
                    items_by_col[6].append(item)
            # Non-weapon cols stay as-is
            for item in items:
                c = item["col"]
                if c in (7, 8):
                    items_by_col[c].append(item)
        else:
            for item in items:
                c = item["col"]
                if c in items_by_col:
                    items_by_col[c].append(item)
                    
        # assign each column
        assignments = {}
        for c, list_items in items_by_col.items():
            if list_items:
                assignments[c] = assign_items_to_bots(bots, list_items)
            else:
                assignments[c] = []
                
        max_rows = len(bots)
        for c in items_by_col.keys():
            max_rows = max(max_rows, len(assignments[c]))
            
        rows = []
        for i in range(max_rows):
            bot_id = bots[i]["vbot"] if i < len(bots) else None
            row = {"botId": bot_id, "cells": {}}
            if bot_id:
                row["cells"]["1"] = f"OBJID_VirtualBot::{bot_id}"
            if i < len(bots):
                if bots[i][2]: row["cells"]["2"] = f"OBJID_Module::{bots[i][2]}"
                if bots[i][3]: row["cells"]["3"] = f"OBJID_Module::{bots[i][3]}"
                if bots[i][4]: row["cells"]["4"] = f"OBJID_Module::{bots[i][4]}"
            for c in items_by_col.keys():
                if i < len(assignments[c]) and assignments[c][i]:
                    row["cells"][str(c)] = f"OBJID_Module::{assignments[c][i]['id']}"
            rows.append(row)
        return rows

    return {
        "standardRows": process_items(standard_modules, is_titan=False),
        "titanRows": process_items(titan_modules, is_titan=True)
    }
