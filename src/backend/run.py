"""
run.py

Main orchestrator script for the backend of WRFrontiers Discount Visualizer.

Usage:
    python src/backend/run.py --items "Item1, Item2" --date-range "mm-dd mm-dd"

Example:
    python src/backend/run.py --items "Phantom, Lighter, Blink" --date-range "06-16 06-23"

All output is logged to timestamped files in logs/ with 14-day auto-retention.
"""

import argparse
import sys
from logger import DiscountLogger
from step1_build_game_data import run_step as run_step1
from step2_map_items import run_step as run_step2
from step3_archive_gen_grid import run_step as run_step3

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the WRFrontiers Discount Visualizer backend workflow."
    )
    parser.add_argument(
        "--items",
        dest="item_names",
        required=True,
        help="Comma-separated item names to map.",
    )
    parser.add_argument(
        "--date-range",
        dest="target_date_range",
        required=True,
        help="Target date range for the discount week, e.g. \"06-16 06-23\".",
    )
    return parser.parse_args()

def main():
    args = parse_args()
    logger = DiscountLogger()

    try:
        item_names = args.item_names.strip()
        target_date_range = args.target_date_range.strip()

        if not item_names:
            logger.error("--items cannot be empty.")
            sys.exit(1)

        if not target_date_range:
            logger.error("--date-range cannot be empty.")
            sys.exit(1)

        logger.start_run(item_names, target_date_range)

        logger.step("Step 1: Build game data")
        run_step1()

        logger.step("Step 2: Map items to game refs")
        run_step2(item_names, target_date_range, logger)

        logger.step("Step 3: Archive and generate grid")
        discounts = run_step3()

        logger.result(f"Successfully mapped {len([i for i in item_names.split(',') if i.strip()])} items for week {target_date_range}. Ready for frontend build.")

    except Exception as e:
        logger.error(str(e))
        raise
    finally:
        logger.close()

if __name__ == "__main__":
    main()

