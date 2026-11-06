"""
discord_event.py

Read a discount week from WRF's Discord scheduled event, given its id.

WRF posts each discount week as a scheduled event, often before the news post.
The public invite endpoint returns the event without any auth:

    GET {DISCORD_API_BASE}/invites/{DISCORD_INVITE_CODE}?guild_scheduled_event_id=<id>

The event's `description` is the announcement text ("War Robot Modules: ...",
"Weapons: ...", "Gear: ..."), parsed by announcement.py, and its scheduled
start/end times give the week's date range.

The id is the last path segment of a discord.com/events/<guild>/<event> link.
"""

import re
from datetime import datetime, timezone

import requests

import config

# Discord ids are 64-bit snowflakes: 17-20 decimal digits in practice.
_SNOWFLAKE_RE = re.compile(r"^\d{17,20}$")
_USER_AGENT = "WRFrontiers-Discount-Visualizer"


class DiscordEventError(ValueError):
    """The event id is invalid, or the event could not be read."""


def fetch_event(event_id: str) -> dict:
    """Return the scheduled-event object for event_id from WRF's Discord server.

    Raises DiscordEventError if the id is not a snowflake, the request fails, the
    event is missing (wrong id, ended or deleted), or it belongs to another server.
    """
    event_id = (event_id or "").strip()
    if not _SNOWFLAKE_RE.match(event_id):
        raise DiscordEventError(
            f'"{event_id}" is not a Discord event id (expected 17-20 digits, the last '
            "path segment of a discord.com/events/<guild>/<event> link)."
        )

    url = f"{config.DISCORD_API_BASE}/invites/{config.DISCORD_INVITE_CODE}"
    try:
        response = requests.get(
            url,
            params={"guild_scheduled_event_id": event_id},
            headers={"User-Agent": _USER_AGENT},
            timeout=config.DISCORD_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as e:
        raise DiscordEventError(f"Could not fetch Discord event {event_id}: {e}") from e

    event = payload.get("guild_scheduled_event")
    if not event:
        raise DiscordEventError(
            f"Discord event {event_id} was not found in the {config.DISCORD_INVITE_CODE} "
            "server; the id may be wrong, or the event has ended or been deleted."
        )

    guild_ids = {payload.get("guild_id"), event.get("guild_id")}
    if guild_ids != {config.DISCORD_GUILD_ID}:
        raise DiscordEventError(
            f"Discord event {event_id} belongs to guild {sorted(g for g in guild_ids if g)}, "
            f"not WRF's {config.DISCORD_GUILD_ID}."
        )
    return event


def event_to_announcement(event: dict) -> str:
    """The event's announcement text, for announcement.announcement_to_items."""
    description = (event.get("description") or "").strip()
    if not description:
        raise DiscordEventError(f"Discord event {event.get('id')} has no description.")
    return description


def _utc_date(value: str, field: str):
    if not value:
        raise DiscordEventError(f"Discord event has no {field}.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as e:
        raise DiscordEventError(f"Discord event {field} is not ISO 8601: {value}") from e
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date()


def event_to_date_range(event: dict) -> str:
    """The event's week as run.py's "mm-dd mm-dd" date range.

    Dates are taken in UTC. An event runs e.g. 2026-11-10T10:00Z to
    2026-11-17T09:45Z, whose UTC dates match the week's announced
    "November 10 - November 17" and its archive slug (2026-11-10, a Tuesday).
    """
    start = _utc_date(event.get("scheduled_start_time"), "scheduled_start_time")
    end = _utc_date(event.get("scheduled_end_time"), "scheduled_end_time")
    return f"{start:%m-%d} {end:%m-%d}"
