"""
run.py

Main orchestrator script for the backend of WRFrontiers Discount Visualizer.

Usage:
    python src/backend/run.py --items "Item1, Item2" --date-range "mm-dd mm-dd"

Example:
    python src/backend/run.py --items "Phantom, Lighter, Blink" --date-range "06-16 06-23"
"""

import argparse
import sys
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

    print("Starting WRFrontiers Discount Visualizer Backend Processing...")

    item_names = args.item_names.strip()
    target_date_range = args.target_date_range.strip()

    if not item_names:
        print("Error: --items cannot be empty.")
        sys.exit(1)
        
    if not target_date_range:
        print("Error: --date-range cannot be empty.")
        sys.exit(1)

    run_step1()
    run_step2(item_names, target_date_range)
    discounts = run_step3()

    print("\nDone! All steps completed successfully. Ready for frontend build.")

if __name__ == "__main__":
    main()

