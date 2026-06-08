"""
run.py

Main orchestrator script for the backend of WRFrontiers Discount Visualizer.
Runs step 1 through 4.

Usage:
    python src/backend/run.py <news_url>

Example:
    python src/backend/run.py https://warrobotsfrontiers.com/en/news/272-intel-salvage-discount-event-save-big-april-14-21
"""

import sys
from step1_scrape import run_step as run_step1
from step2_build_game_data import run_step as run_step2
from step3_call_gemini import run_step as run_step3
from step4_archive_gen_grid import run_step as run_step4

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/backend/run.py <news_url> [target_date_range]")
        print(
            "Example: python src/backend/run.py "
            "https://warrobotsfrontiers.com/en/news/272-intel-salvage-discount-event-save-big-april-14-21 "
            "\"May 26 - June 2\""
        )
        sys.exit(1)

    url = sys.argv[1]
    target_date_range = sys.argv[2] if len(sys.argv) > 2 else None

    print("Starting WRFrontiers Discount Visualizer Backend Processing...")
    
    # Step 1: Scrape news article
    run_step1(url)

    # Step 2: Build game data database excerpt
    run_step2()

    # Step 3: Run Gemini model mapping
    run_step3(target_date_range)

    # Step 4: Validate and load the mapped output
    discounts = run_step4()

    print("\nDone! All steps completed successfully. Ready for frontend build.")

if __name__ == "__main__":
    main()

