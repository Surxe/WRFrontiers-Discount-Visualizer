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
from level_discount import LevelDiscountClassifier
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
    parser.add_argument(
        "--level-discount-note",
        dest="level_discount_note",
        default="",
        help="Optional natural-language note restricting which levels the discount "
             "applies to (e.g. \"available only for items at level 9 or higher\"). "
             "Classified into a start/end level range; an unclassifiable note fails "
             "the run.",
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


def classify_level_discount(note: str, logger) -> dict | None:
    """Classify the level-discount note into {"start", "end"}, or fail the run.

    An empty note means "all levels" (returns None, no restriction). A non-empty
    note that cannot be represented as a start/end range (the LLM's "neither"
    outcome) is an error: it exits non-zero and quotes the note so the failure is
    visible in the run log and the orchestrator's email.
    """
    note = (note or "").strip()
    if not note:
        return None

    classifier = LevelDiscountClassifier()
    if not classifier.available:
        msg = (f"A level-discount note was provided but JEV_API_KEY is not set; "
               f"cannot classify: \"{note}\"")
        print(f"[ERROR] {msg}")   # [ERROR] so the CI log grep (and the email) picks it up
        logger.error(msg)
        sys.exit(1)

    level_discount = classifier.classify(note)
    classifier.close()
    if level_discount is None:
        msg = (f"Could not represent this week's level-discount note as a "
               f"start/end level range: \"{note}\"")
        print(f"[ERROR] {msg}")   # [ERROR] so the CI log grep (and the email) picks it up
        logger.error(msg)
        sys.exit(1)

    logger.info(f"Level discount classified: level {level_discount['start']}->"
                f"{level_discount['start'] + 1} through "
                f"{level_discount['end'] - 1}->{level_discount['end']} "
                f"(start={level_discount['start']}, end={level_discount['end']})")
    return level_discount


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

        level_discount = classify_level_discount(args.level_discount_note, logger)

        logger.start_run(item_names, target_date_range)

        logger.step("Step 1: Build game data")
        run_step1()

        logger.step("Step 2: Map items to game refs")
        run_step2(item_names, target_date_range, logger, level_discount=level_discount)

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

