import sys
import json
import re
from pathlib import Path
from config import DISCOUNTS_OUTPUT, GAME_DATA_JSON, REPO_ROOT, FRONTEND_DATA_DIR

def load_discounts() -> list[dict]:
    """
    Reads the LLM-generated discounts.json output (which is a list of IDs).
    Reconstitutes the full metadata (name, image_path) by looking them up in game_data.json.
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

    # Load game_data.json to build a lookup map
    if not GAME_DATA_JSON.exists():
        print(f"  [ERROR] game_data.json not found at {GAME_DATA_JSON}")
        sys.exit(1)

    with open(GAME_DATA_JSON, encoding="utf-8") as f:
        game_data = json.load(f)

    # Map ID -> full details
    game_data_map = {item["id"]: item for item in game_data}

    discounts = []
    for m_ref in discount_refs:
        # Gracefully handle string IDs or list items
        if not isinstance(m_ref, str):
            continue
        
        match = game_data_map.get(m_ref)
        if match:
            discounts.append(match)
            print(f"     • Resolved: {match['name']} ({match['id']})")
        else:
            print(f"     [!] Warning: ID {m_ref} from LLM output was not found in game_data.json")

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
