"""
level_discount.py

Classify a weekly level-restriction note into a start/end level range using
TypeSafe AI's Jev model (the same closed-set classifier that maps item names).

WRF began tagging some weeks with a natural-language restriction, e.g.:

    "This week's upgrade discounts are available only for items at level 9 or higher."

The scraper extracts that sentence verbatim; this module turns it into the
structured range the site and cost calculator need, or None when the note can't
be represented as one contiguous start/end range (the "neither" outcome, which
errors the deployment).

Range semantics (documented once, used everywhere):

    ``{"start": S, "end": E}`` means the discounted upgrades are ``S -> S+1``
    through ``E-1 -> E``. ``start`` is the lowest item level whose upgrade to the
    next level is discounted (the "from" level), and ``end`` is the highest level
    a discounted upgrade produces. So the phrase "level 9 or higher" maps to
    ``{"start": 8, "end": 13}``: the in-game discount covers the 8->9 upgrade
    through the 12->13 upgrade, NOT the 7->8 upgrade.

Two Choice questions ("start", "end") are asked in one system_one call, each over
the closed set {level 1..13, "none"}. "none" is the escape hatch: when the note
cannot be represented as a single contiguous range the model picks "none", and
``classify()`` returns None (the caller then fails the run and quotes the note).
"""

from __future__ import annotations

import os

# The closed set for each question: levels 1..13 plus the "unrepresentable" escape.
LEVEL_OPTIONS = {str(i): f"level {i}" for i in range(1, 14)}
LEVEL_OPTIONS["none"] = (
    "no single level - the note cannot be represented as a start/end range"
)

_START_INSTRUCTIONS = (
    "Given a note about which item levels a weekly upgrade discount applies to, "
    "choose the LOWEST item level whose upgrade to the next level is discounted "
    "(the 'from' level of the first discounted upgrade). WRF's phrase 'items at "
    "level 9 or higher' (or '9 and up') means the 8->9 upgrade is discounted too, "
    "so the start is level 8, NOT level 9. Choose 'none' only if the note cannot "
    "be represented as a single contiguous level range."
)

_END_INSTRUCTIONS = (
    "Given a note about which item levels a weekly upgrade discount applies to, "
    "choose the HIGHEST level a discounted upgrade produces. WRF's phrase 'items "
    "at level 9 or higher' (or '9 and up') runs through the 12->13 upgrade, so the "
    "end is level 13. Choose 'none' only if the note cannot be represented as a "
    "single contiguous level range."
)


class LevelDiscountClassifier:
    """Classify a level-restriction note into ``{"start": S, "end": E}`` or None.

    A ``client`` may be injected (for tests); otherwise a real TypeSafeClient is
    built lazily from ``api_key`` (default: the JEV_API_KEY env var) on first use.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None, client=None):
        self._api_key = api_key if api_key is not None else os.environ.get("JEV_API_KEY")
        self._model = model
        self._client = client

    @property
    def available(self) -> bool:
        """True if a classification call could be made (a client or a key is present)."""
        return self._client is not None or bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            import typesafe_sdk as t  # lazy: import only when Jev is actually used

            self._client = t.TypeSafeClient(api_key=self._api_key, model=self._model)
        return self._client

    def _ask(self, note: str) -> tuple[str, str]:
        """One system_one call; returns (start_choice, end_choice)."""
        import typesafe_sdk as t

        client = self._get_client()
        resp = client.system_one(
            state={"level_note": note},
            questions={
                "start": t.Choice(instructions=_START_INSTRUCTIONS, criteria=LEVEL_OPTIONS),
                "end": t.Choice(instructions=_END_INSTRUCTIONS, criteria=LEVEL_OPTIONS),
            },
        )
        return resp.answers["start"].choice, resp.answers["end"].choice

    def classify(self, note: str | None) -> dict | None:
        """Return ``{"start": S, "end": E}`` for the note, or None if unrepresentable.

        None is also returned for an empty note and for any answer that isn't a
        valid, strictly increasing 1..13 range (including the "none" escape hatch).
        """
        text = (note or "").strip()
        if not text:
            return None
        start, end = self._ask(text)
        if start == "none" or end == "none":
            return None
        try:
            s, e = int(start), int(end)
        except (TypeError, ValueError):
            return None
        if not (1 <= s < e <= 13):
            return None
        return {"start": s, "end": e}

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
