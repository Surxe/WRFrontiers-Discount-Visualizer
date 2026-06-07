"""
step3_call_gemini.py

Step 3: Call the Gemini CLI with access to prompt/ directory to map items.
"""

import sys
import shutil
import subprocess
from datetime import datetime
from config import PROMPT_DIR, OUTPUT_DIR, DISCOUNTS_OUTPUT

def call_gemini_cli(target_date_range: str | None = None):
    """
    Invokes the Gemini CLI via subprocess.
    Captures the raw JSON printed to stdout and writes it to prompt/output/discounts.json.
    """
    print("[3/4] Calling Gemini CLI...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build the prompt message that references the files
    current_year = datetime.now().year

    prompt_message = (
        "Follow the instructions at prompt.md in src/backend/prompt/. "
        "Read scraped_news_page.txt and game_data.json from the current directory, "
        "and output the resulting JSON directly to stdout without using file editing tools. "
        f"The current year for date normalization is {current_year}. "
        "If a discount range starts in December and ends in January, use the following year for the end date."
    )
    if target_date_range:
        prompt_message += (
            f" The target date range is: \"{target_date_range}\". "
            "Locate and extract the Featured Items section matching this date range instead of the most recent one. "
            "Standardize the date range to match the formatting rules in prompt.md."
        )

    # Try 'gemini' (globally installed) then fall back to npx
    gemini_cmd = shutil.which("gemini")
    if gemini_cmd:
        cmd = [gemini_cmd, "--skip-trust", "--prompt", prompt_message]
    else:
        cmd = ["npx", "--yes", "@google/gemini-cli", "--skip-trust", "--prompt", prompt_message]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROMPT_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"  [ERROR] Gemini CLI exited with code {result.returncode}")
            print(f"  STDOUT: {result.stdout}")
            print(f"  STDERR: {result.stderr}")
            sys.exit(1)
        
        # Write captured stdout to the discounts.json file
        output_content = result.stdout.strip()
        DISCOUNTS_OUTPUT.write_text(output_content, encoding="utf-8")
        
        print(f"  -> Gemini CLI completed successfully and output was saved to {DISCOUNTS_OUTPUT.name}.")
    except FileNotFoundError:
        print(
            "  [ERROR] 'gemini' CLI not found. "
            "Install it with: npm install -g @google/gemini-cli"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("  [ERROR] Gemini CLI timed out after 300 seconds.")
        sys.exit(1)


def run_step(target_date_range: str | None = None):
    call_gemini_cli(target_date_range)


if __name__ == "__main__":
    # If run standalone, we can optionally parse target_date_range from sys.argv
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_step(arg)

