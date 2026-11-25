import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from level_discount import LevelDiscountClassifier, LEVEL_OPTIONS  # noqa: E402


class ScriptedClient:
    """A fake TypeSafeClient whose per-note answers are scripted."""

    def __init__(self, answers):
        self.answers = answers  # note -> (start_choice, end_choice)
        self.calls = []
        self.closed = False

    def system_one(self, state, questions):
        self.calls.append(state)
        start, end = self.answers[state["level_note"]]
        return SimpleNamespace(answers={
            "start": SimpleNamespace(choice=start),
            "end": SimpleNamespace(choice=end),
        })

    def close(self):
        self.closed = True


class TestClassify(unittest.TestCase):
    def test_level_9_or_higher_maps_to_8_to_13(self):
        c = LevelDiscountClassifier(client=ScriptedClient(
            {"items at level 9 or higher": ("8", "13")}))
        self.assertEqual(
            c.classify("items at level 9 or higher"),
            {"start": 8, "end": 13},
        )

    def test_full_range_is_1_to_13(self):
        c = LevelDiscountClassifier(client=ScriptedClient(
            {"all levels": ("1", "13")}))
        self.assertEqual(c.classify("all levels"), {"start": 1, "end": 13})

    def test_none_escape_hatch_returns_none(self):
        for start, end in [("none", "13"), ("8", "none"), ("none", "none")]:
            c = LevelDiscountClassifier(client=ScriptedClient(
                {"weird": (start, end)}))
            self.assertIsNone(c.classify("weird"))

    def test_inverted_or_single_level_range_is_none(self):
        for start, end in [("10", "8"), ("8", "8"), ("0", "13"), ("14", "13")]:
            c = LevelDiscountClassifier(client=ScriptedClient(
                {"n": (start, end)}))
            self.assertIsNone(c.classify("n"))

    def test_non_numeric_answer_is_none(self):
        c = LevelDiscountClassifier(client=ScriptedClient({"n": ("eight", "13")}))
        self.assertIsNone(c.classify("n"))

    def test_empty_note_returns_none_without_a_call(self):
        client = ScriptedClient({})
        c = LevelDiscountClassifier(client=client)
        self.assertIsNone(c.classify("   "))
        self.assertEqual(client.calls, [])

    def test_available_reflects_key(self):
        self.assertTrue(LevelDiscountClassifier(api_key="k").available)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JEV_API_KEY", None)
            self.assertFalse(LevelDiscountClassifier(api_key=None).available)

    def test_options_cover_all_levels_plus_none(self):
        self.assertEqual(set(LEVEL_OPTIONS), {str(i) for i in range(1, 14)} | {"none"})


if __name__ == "__main__":
    unittest.main()
