import sys
import json
import re
from pathlib import Path
from config import DISCOUNTS_OUTPUT, MODULE_JSON, VIRTUAL_BOT_JSON, REPO_ROOT, FRONTEND_DATA_DIR

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
    Extracts id, name, and image_path from a Module dictionary.
    """
    module = modules_data.get(module_id)
    if not module:
        return None
    
    name_field = module.get("name", {})
    english_name = name_field.get("en", "")
    icon_path = module.get("inventory_icon_path", "")
    
    if english_name and icon_path:
        return {
            "id": module_id,
            "name": english_name,
            "image_path": icon_path.lstrip("/")
        }
    return None

def load_discounts() -> list[dict]:
    """
    Reads the LLM-generated discounts.json output (which is a list of refs).
    Reconstitutes the full metadata by looking them up directly in Module.json and VirtualBot.json.
    For VirtualBot objtypes, expands to its core modules.
    Writes the result to frontend public/data/discounts.json.
    """
    print("[4/4] Reading LLM output from prompt/output/discounts.json...")

    if not DISCOUNTS_OUTPUT.exists():
        print(f"  [ERROR] Output file not found: {DISCOUNTS_OUTPUT}")
        print("  The Gemini CLI may not have written the output file.")
        sys.exit(1)

    with open(DISCOUNTS_OUTPUT, encoding="utf-8") as f:
        content = f.read().strip()

    # Strip markdown code fences if the LLM wrapped the JSON
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        discount_refs = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  [ERROR] Output is not valid JSON: {e}")
        print(f"  Content preview: {content[:300]}")
        sys.exit(1)

    if not isinstance(discount_refs, list):
        print("  [ERROR] Output is not a JSON list/array.")
        sys.exit(1)

    print(f"  -> Found {len(discount_refs)} ID matches in output.")

    # Load constant JSONs
    if not MODULE_JSON.exists() or not VIRTUAL_BOT_JSON.exists():
        print(f"  [ERROR] Database JSONs not found.")
        sys.exit(1)

    with open(MODULE_JSON, encoding="utf-8") as f:
        modules_data = json.load(f)

    with open(VIRTUAL_BOT_JSON, encoding="utf-8") as f:
        virtual_bots_data = json.load(f)

    discounts = []
    for m_ref in discount_refs:
        if not isinstance(m_ref, str):
            continue
        
        obj_type, obj_id = parse_ref(m_ref)
        
        if obj_type == "VirtualBot":
            vbot = virtual_bots_data.get(obj_id)
            if vbot:
                print(f"     • Resolved VirtualBot: {obj_id}")
                # Groups included as standalone items in step2 — exclude them
                # here so titan-specific weapons (e.g. Norna's Coriolis) are not listed unless explicitly listed as a weapon
                # in the discount list.
                EXCLUDED_MODULE_GROUPS = [
                    "supply-gear", "cycle-gear",
                    "light-weapon", "heavy-weapon", "titan-weapon",
                ]
                for core_ref in vbot.get("core_module_refs", []):
                    c_type, c_id = parse_ref(core_ref)
                    module = modules_data.get(c_id)
                    if not module:
                        continue
                    group_ref = module.get("module_group_ref", "")
                    if any(group in group_ref for group in EXCLUDED_MODULE_GROUPS):
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

    # Write the full discounts data to frontend
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    frontend_output = FRONTEND_DATA_DIR / "discounts.json"
    with open(frontend_output, "w", encoding="utf-8") as f:
        json.dump(discounts, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote {len(discounts)} items to {frontend_output.relative_to(REPO_ROOT)}")

    return discounts

def run_step() -> list[dict]:
    return load_discounts()

if __name__ == "__main__":
    run_step()
