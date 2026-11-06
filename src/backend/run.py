"""
run.py

Main orchestrator script for the backend of WRFrontiers Discount Visualizer.

Usage:
    python src/backend/run.py --items "Item1, Item2" --date-range "mm-dd mm-dd"
    python src/backend/run.py --event-id <discord event id> [--date-range "mm-dd mm-dd"]

Give exactly one of --items or --event-id. --event-id reads WRF's Discord
scheduled event (discord_event.py) and parses its description as the
announcement (announcement.py). --date-range is required with --items; with
--event-id it defaults to the event's dates, and an explicit one wins.

Example:
    python src/backend/run.py --items "Phantom, Lighter, Blink" --date-range "06-16 06-23"
    python src/backend/run.py --event-id 1568259964999565422

All output is logged to timestamped files in logs/ with 14-day auto-retention.
"""

import argparse
import sys
from announcement import announcement_to_items
import discord_event
from logger import DiscountLogger
from step1_build_game_data import run_step as run_step1
from step2_map_items import run_step as run_step2
from step3_archive_gen_grid import run_step as run_step3

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the WRFrontiers Discount Visualizer backend workflow."
    )
    parser.add_argument(
        "--items",
        dest="item_names",
        default="",
        help="Comma-separated item names to map. Give this or --event-id.",
    )
    parser.add_argument(
        "--event-id",
        default="",
        help="Discord scheduled-event id of the discount week (the last path segment "
             "of a discord.com/events/<guild>/<event> link). Give this or --items.",
    )
    parser.add_argument(
        "--date-range",
        dest="target_date_range",
        default="",
        help="Target date range for the discount week, e.g. \"06-16 06-23\". "
             "Required with --items; defaults to the event's dates with --event-id.",
    )
    return parser.parse_args(argv)


def resolve_inputs(item_names: str, event_id: str, date_range: str, logger):
    """Return (comma-separated items, "mm-dd mm-dd") from exactly one item source.

    Raises ValueError with a user-facing message on bad or conflicting inputs.
    """
    item_names, event_id, date_range = (
        (v or "").strip() for v in (item_names, event_id, date_range)
    )
    if sum(bool(v) for v in (item_names, event_id)) != 1:
        raise ValueError("Give exactly one of --items or --event-id.")

    if event_id:
        event = discord_event.fetch_event(event_id)
        logger.info(f"Discord event {event_id}: {event.get('name')}")
        try:
            item_names = announcement_to_items(discord_event.event_to_announcement(event))
        except ValueError as e:
            raise ValueError(f"Could not parse Discord event {event_id}'s description: {e}") from e
        event_range = discord_event.event_to_date_range(event)
        if not date_range:
            date_range = event_range
        elif date_range != event_range:
            logger.warning(
                f"--date-range {date_range} differs from the event's dates {event_range}; "
                "using --date-range."
            )

    if not date_range:
        raise ValueError("--date-range is required with --items.")
    return item_names, date_range


def main():
    args = parse_args()
    logger = DiscountLogger()

    try:
        try:
            item_names, target_date_range = resolve_inputs(
                args.item_names, args.event_id, args.target_date_range, logger
            )
        except ValueError as e:
            logger.error(str(e))
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

