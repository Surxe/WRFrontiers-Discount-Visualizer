"""
step4_read_output.py

Step 4: Read the LLM output from prompt/output/discounts.json.
"""

import sys
import json
import re
from config import DISCOUNTS_OUTPUT, REPO_ROOT

def load_discounts() -> list[dict]:
    """
    Reads the LLM-generated discounts.json output.
    Validates that it is a non-empty list with the expected fields.
    """
    print("[4/5] Reading LLM output from prompt/output/discounts.json...")

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
        discounts = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  [ERROR] Output is not valid JSON: {e}")
        print(f"  Content preview: {content[:300]}")
        sys.exit(1)

    if not isinstance(discounts, list) or len(discounts) == 0:
        print("  [ERROR] Output is empty or not a JSON array.")
        sys.exit(1)

    print(f"  -> {len(discounts)} discounted items found:")
    for item in discounts:
        print(f"     • {item.get('name', '?')} ({item.get('id', '?')})")

    return discounts


def run_step() -> list[dict]:
    return load_discounts()


if __name__ == "__main__":
    run_step()
