"""
step3_call_gemini.py

Step 3: Call the Gemini CLI with access to prompt/ directory to map items.
"""

import sys
import shutil
import subprocess
from config import PROMPT_DIR, OUTPUT_DIR

def call_gemini_cli():
    """
    Invokes the Gemini CLI via subprocess.
    The CLI is given access to the prompt/ directory and instructed to follow prompt.md.
    It should write output to prompt/output/discounts.json.
    """
    print("[3/5] Calling Gemini CLI...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build the prompt message that references the files
    prompt_message = (
        "Follow the instructions in prompt.md. "
        "Read scraped_news_page.txt and game_data.json from the current directory, "
        "then write the output JSON array to output/discounts.json."
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
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  [ERROR] Gemini CLI exited with code {result.returncode}")
            print(f"  STDOUT: {result.stdout}")
            print(f"  STDERR: {result.stderr}")
            sys.exit(1)
        print(f"  -> Gemini CLI completed successfully.")
        if result.stdout:
            print(f"  STDOUT: {result.stdout[:500]}")
    except FileNotFoundError:
        print(
            "  [ERROR] 'gemini' CLI not found. "
            "Install it with: npm install -g @google/gemini-cli"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("  [ERROR] Gemini CLI timed out after 120 seconds.")
        sys.exit(1)


def run_step():
    call_gemini_cli()


if __name__ == "__main__":
    run_step()
