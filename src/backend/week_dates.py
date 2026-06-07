from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


MONTHS_LONG = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

MONTH_LOOKUP = {
    month.lower(): index + 1 for index, month in enumerate(MONTHS_LONG)
} | {
    month.lower(): index + 1 for index, month in enumerate(MONTHS_SHORT)
}


def _month_number(month: str | int) -> int:
    if isinstance(month, int):
        if 1 <= month <= 12:
            return month
        raise ValueError(f"Invalid month number: {month}")

    key = month.strip().lower()
    if key in MONTH_LOOKUP:
        return MONTH_LOOKUP[key]
    key = key[:3]
    if key in MONTH_LOOKUP:
        return MONTH_LOOKUP[key]
    raise ValueError(f"Invalid month name: {month}")


def _parse_date_part(part: str, fallback_month: int | None = None, fallback_year: int | None = None) -> dict[str, int]:
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", part.strip(), flags=re.IGNORECASE)
    match = re.search(r"([A-Za-z]+)?\s*(\d{1,2})(?:,?\s*(\d{4}))?", cleaned)
    if not match:
        raise ValueError(f"Could not parse date part: {part}")

    month_text, day_text, year_text = match.groups()
    if month_text:
        month = _month_number(month_text)
    elif fallback_month:
        month = fallback_month
    else:
        raise ValueError(f"Missing month in date part: {part}")

    year = int(year_text) if year_text else fallback_year
    if year is None:
        year = datetime.now().year

    return {"year": year, "month": month, "day": int(day_text)}


def normalize_week(value: dict[str, Any] | str) -> dict[str, int]:
    if isinstance(value, dict) and all(
        key in value
        for key in ("start_month", "start_day", "end_month", "end_day")
    ) and "start_year" not in value:
        start_month = _month_number(value["start_month"])
        end_month = _month_number(value["end_month"])
        current_year = datetime.now().year
        
        start_year = current_year
        end_year = current_year
        
        if end_month < start_month:
            end_year = start_year + 1
        
        return {
            "start_year": start_year,
            "start_month": start_month,
            "start_day": int(value["start_day"]),
            "end_year": end_year,
            "end_month": end_month,
            "end_day": int(value["end_day"]),
        }

    if isinstance(value, dict) and "date_range" in value:
        value = value["date_range"]

    if not isinstance(value, str):
        raise ValueError("Week value must be a structured week object or date range string")

    parts = re.split(r"\s+[-–—]\s+", value.strip(), maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Could not parse date range: {value}")

    current_year = datetime.now().year
    start = _parse_date_part(parts[0], fallback_year=current_year)
    end = _parse_date_part(parts[1], fallback_month=start["month"], fallback_year=start["year"])

    if end["month"] == 1 and start["month"] == 12 and "2026" not in parts[1] and "2027" not in parts[1]:
        end["year"] = start["year"] + 1
    elif date(end["year"], end["month"], end["day"]) < date(start["year"], start["month"], start["day"]):
        end["year"] += 1

    return {
        "start_year": start["year"],
        "start_month": start["month"],
        "start_day": start["day"],
        "end_year": end["year"],
        "end_month": end["month"],
        "end_day": end["day"],
    }


def week_slug(week: dict[str, Any]) -> str:
    normalized = normalize_week(week)
    return f"{normalized['start_year']:04d}-{normalized['start_month']:02d}-{normalized['start_day']:02d}"


def week_sort_key(week: dict[str, Any]) -> tuple[int, int, int]:
    normalized = normalize_week(week)
    return (normalized["start_year"], normalized["start_month"], normalized["start_day"])


def format_week(week: dict[str, Any], style: str = "long") -> str:
    normalized = normalize_week(week)
    month_names = MONTHS_SHORT if style == "short" else MONTHS_LONG
    start_month = month_names[normalized["start_month"] - 1]
    end_month = month_names[normalized["end_month"] - 1]

    start = f"{start_month} {normalized['start_day']}"
    if normalized["start_month"] == normalized["end_month"]:
        end = str(normalized["end_day"])
    else:
        end = f"{end_month} {normalized['end_day']}"

    if style == "short":
        return f"{start} - {end}"

    if normalized["start_year"] == normalized["end_year"]:
        return f"{start} - {end} ({normalized['start_year']})"

    return (
        f"{start} {normalized['start_year']} - "
        f"{end_month} {normalized['end_day']} {normalized['end_year']}"
    )
