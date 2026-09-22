"""
jev_mapper.py

LLM name->game-id mapping via TypeSafe AI's Jev "System One" model.

Re-adds the mapping intelligence that was removed with the Gemini step
(step3_call_gemini.py, deleted in 9779159 "Refactor mapping pipeline to use local
fuzzy matching"), but reworked around Jev instead of a conversational LLM.

Why Jev fits this job better than a chat model:
  * The answer space is a *closed set* -- the ~119 entries of game_data.json. Jev's
    `Choice` primitive picks exactly one option from a supplied set (up to 255) and
    is mathematically incapable of returning anything outside it, so it can never
    hallucinate a ref that does not exist (the classic free-form-LLM failure here).
  * It is a pure input->typed-output transform (no conversation), which is exactly
    the shape of "map this announced name to a game id".
  * Every answer carries a calibrated confidence, so a genuinely unknown name (a
    brand-new robot not yet in game_data) scores low and is surfaced for review
    instead of being silently mis-mapped.

The one limitation is single-select: a mis-split announcement token -- e.g. the
scraper handing "Ceresm Norna" as a single item when it is really "Ceres" + "Norna"
-- can only map to one ref on its own. We detect and repair that: such a token is
not an exact vocab name and, when split on whitespace, its pieces each resolve to a
distinct high-confidence ref, so we expand it to both. Genuine multi-word names
("Kinetic Pulse", "Ghost Turret") are exact vocab entries and are never split.

No API key: the mapper reports itself unavailable. perform_mapping then resolves only
manual pins and exact vocab matches (so unit tests can run without a key); the CLI
entry point (map_items) fails fast, since Jev is the mapper for real runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Accept a whole-token Jev answer at/above this confidence. Calibrated against the 10
# latest discount weeks (130 items, see the calibration run): every genuine single name
# scored >= 0.94 (typos included) while out-of-vocab / unknown names topped out at 0.37,
# leaving a wide empty band. 0.7 sits mid-gap -- it rejects no real name seen yet keeps
# ~0.33 clearance above noise, so a brand-new unknown item is surfaced for a manual pin
# (a loud, one-time failure) instead of being silently mis-mapped (quiet corruption).
DEFAULT_ACCEPT_THRESHOLD = 0.7
# Only reconstruct a mis-split when every piece maps this confidently; keeps us from
# shredding a genuine (but slightly typo'd) multi-word name into noise. The one observed
# mis-split ("Ceresm Norna") had both pieces >= 0.99, far above this, so 0.75 has margin.
DEFAULT_SPLIT_PIECE_THRESHOLD = 0.75

# Prompt engineering note: the vocab carries variant twins that share a base name but are
# SEPARATE items -- most commonly a "Relic <X>" alongside the plain "<X>" (e.g. "Relic
# Thunder" vs "Thunder"). The distinguishing word is often the only difference, so its
# presence *and its absence* both carry meaning. We tell the model to read that negative
# space: a qualifier that is present selects the variant; a qualifier that is absent
# selects the base, never the variant. Without this, a fuzzy/typo'd base name can leak
# probability onto its Relic twin (and vice versa).
DEFAULT_INSTRUCTIONS = (
    "This is one item name taken from a War Robots: Frontiers discount announcement. "
    "It may contain typos, plural forms, or informal spelling; correct for those and "
    "select the single game item (robot, weapon, or gear) it refers to.\n"
    "Match qualifier words exactly -- by their absence as well as their presence. Some "
    "items exist as distinct variants set apart by an extra word, above all the prefix "
    "'Relic': 'Relic Thunder' is its own standalone item, NOT another name for the base "
    "'Thunder'. So choose a variant ONLY when the announced name actually carries that "
    "word, and choose the plain base item when it does not. A name with no 'Relic' (or "
    "other qualifier) means the base item is intended -- never fall through to the "
    "variant just because the base word matches. Likewise, do not strip a qualifier that "
    "is present: an announced 'Relic <X>' must map to the Relic variant, not the base."
)


@dataclass
class Resolution:
    """The outcome of resolving one announced name."""

    name: str
    refs: list[str]
    confidence: float
    method: str  # "jev" | "jev-split" | "unmapped"
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.refs)


def _topn(probabilities: dict[str, float], n: int = 3) -> list[tuple[str, float]]:
    return sorted(probabilities.items(), key=lambda kv: -kv[1])[:n]


class JevMapper:
    """Resolve announced item names to game_data refs using Jev `Choice`.

    A `client` may be injected (for tests); otherwise a real TypeSafeClient is built
    lazily from `api_key` (default: the JEV_API_KEY env var) on first use.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        accept_threshold: float = DEFAULT_ACCEPT_THRESHOLD,
        split_piece_threshold: float = DEFAULT_SPLIT_PIECE_THRESHOLD,
        instructions: str = DEFAULT_INSTRUCTIONS,
        client=None,
    ):
        self._api_key = api_key if api_key is not None else os.environ.get("JEV_API_KEY")
        self._model = model
        self._client = client
        self.accept_threshold = accept_threshold
        self.split_piece_threshold = split_piece_threshold
        self.instructions = instructions

    @property
    def available(self) -> bool:
        """True if a mapping call could be made (a client or a key is present)."""
        return self._client is not None or bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            import typesafe_sdk as t  # lazy: import only when Jev is actually used

            self._client = t.TypeSafeClient(api_key=self._api_key, model=self._model)
        return self._client

    def _choice(self, name: str, criteria: dict[str, str]) -> tuple[str, float, dict[str, float]]:
        """One Jev Choice call: returns (chosen_ref, confidence, probability_map)."""
        import typesafe_sdk as t

        client = self._get_client()
        resp = client.system_one(
            state={"listing_name": name},
            questions={"item": t.Choice(instructions=self.instructions, criteria=criteria)},
        )
        a = resp.answers["item"]
        return a.choice, a.confidence, a.probabilities

    def resolve(self, name: str, criteria: dict[str, str]) -> Resolution:
        """Resolve one announced name against the {ref: display_name} vocabulary.

        Tries the whole token first, then -- for a non-vocab multi-word token -- a
        whitespace split, preferring the split only when it yields >= 2 distinct
        pieces that each clear split_piece_threshold (the mis-split case).
        """
        token = name.strip()
        ref, conf, probs = self._choice(token, criteria)

        vocab_names_lower = {v.strip().lower() for v in criteria.values()}
        is_exact_vocab = token.lower() in vocab_names_lower
        words = token.split()

        if not is_exact_vocab and len(words) >= 2:
            piece_results = [self._choice(w, criteria) for w in words]
            if all(c >= self.split_piece_threshold for _, c, _ in piece_results):
                piece_refs = [r for r, _, _ in piece_results]
                if len(set(piece_refs)) == len(piece_refs) >= 2:
                    return Resolution(
                        name=name,
                        refs=piece_refs,
                        confidence=min(c for _, c, _ in piece_results),
                        method="jev-split",
                        detail={"pieces": list(zip(words, piece_refs))},
                    )

        if conf >= self.accept_threshold:
            return Resolution(name, [ref], conf, "jev", {"top": _topn(probs)})
        return Resolution(name, [], conf, "unmapped", {"best": ref, "top": _topn(probs)})

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
