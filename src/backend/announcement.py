"""
announcement.py

Parse a discount announcement into the comma-separated item list that step 2
maps. This is the same text WRF posts on the news page and as the Discord
scheduled event's description (read by discord_event.py):

    This week, the Tortuga engineers invite Pilots to take a closer look at the following builds:

    War Robot Modules: Heike, Orochi, Varangian

    Weapons: Thunder, Zeus, Orkan, Apollo

    Gear: Blast Wave, Recon Mode, Fuel Burn, Flashbang, Ghost Turret, Gamma Beam

Parsing is anchored on the category labels followed by a colon, so anything
before the first label (the "This week, ..." lead-in, or nothing at all) is
ignored. It also tolerates:

  * the newlines being stripped (e.g. text pasted into a single-line input,
    "...VarangianWeapons: ..."); a category's names then run up to the next label,
  * Discord/markdown decoration: bullets ("-", "*", "•") and bold ("**Gear**:").

A category's names end at the next label or at the end of its line, so trailing
text on a later line (a sign-off) is dropped when newlines survive.
"""

import re

# Order is the announcement order; it is also the output order.
CATEGORY_LABELS = ("War Robot Modules", "Weapons", "Gear")

# A label, optionally closed by markdown bold, then a colon. No left word
# boundary: with newlines stripped the label is glued to the previous name.
_LABEL_RE = re.compile(
    r"(" + "|".join(re.escape(label) for label in CATEGORY_LABELS) + r")\s*\**\s*:",
    re.IGNORECASE,
)
# Decoration to trim from each name.
_TRIM = " \t*_•-"


def parse_announcement(text: str) -> dict[str, list[str]]:
    """Return {label: [names]} for each category found in the announcement.

    Raises ValueError if no category label is found, or if a label appears more
    than once (e.g. two weeks pasted together), so the wrong week is never mapped.
    """
    matches = list(_LABEL_RE.finditer(text or ""))
    if not matches:
        raise ValueError(
            "No category labels found in the announcement; expected lines like "
            + ", ".join(f'"{label}: ..."' for label in CATEGORY_LABELS) + "."
        )

    categories: dict[str, list[str]] = {}
    for i, match in enumerate(matches):
        label = next(l for l in CATEGORY_LABELS if l.lower() == match.group(1).lower())
        if label in categories:
            raise ValueError(
                f'Category "{label}" appears more than once; paste a single week only.'
            )
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[match.end():end].strip().splitlines()
        line = segment[0] if segment else ""
        names = [n.strip(_TRIM) for n in line.split(",")]
        categories[label] = [n for n in names if n]
    return categories


def announcement_to_items(text: str) -> str:
    """The announcement's item names as the comma-separated string step 2 expects."""
    categories = parse_announcement(text)
    items = [name for label in CATEGORY_LABELS for name in categories.get(label, [])]
    if not items:
        raise ValueError("The announcement's categories contain no item names.")
    return ", ".join(items)
