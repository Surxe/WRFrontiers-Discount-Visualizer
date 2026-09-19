import os
import sys
import unittest
from unittest import mock

# Add src/backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from jev_mapper import JevMapper, Resolution
from step2_map_items import perform_mapping


# A small vocab; two-word names ("Kinetic Pulse", "Ghost Turret") are exact entries
# so they are never split, exactly like the real game_data.json.
GAME_DATA = [
    {"ref": "OBJID_VirtualBot::ceres", "name": "Ceres"},
    {"ref": "OBJID_VirtualBot::norna", "name": "Norna"},
    {"ref": "OBJID_VirtualBot::phantom", "name": "Phantom"},
    {"ref": "OBJID_Module::DA_Module_Weapon_Orkan.0", "name": "Orkan"},
    {"ref": "OBJID_Module::DA_Module_Ability_Atrophy.1", "name": "Suppressor"},
    {"ref": "OBJID_Module::DA_Module_Ability_KineticPulse.1", "name": "Kinetic Pulse"},
    {"ref": "OBJID_Module::DA_Module_Ability_GhostTurret.1", "name": "Ghost Turret"},
]
CRITERIA = {e["ref"]: e["name"] for e in GAME_DATA}


class ScriptedJev(JevMapper):
    """A JevMapper whose per-name Choice answers are scripted, so resolve()'s
    accept / reject / mis-split logic can be tested without any network or SDK."""

    def __init__(self, answers, **kw):
        super().__init__(api_key="test-key", **kw)
        self.answers = answers  # name -> (ref, confidence)
        self.calls = []

    def _choice(self, name, criteria):
        self.calls.append(name)
        ref, conf = self.answers[name]
        return ref, conf, {ref: conf}


class TestJevResolve(unittest.TestCase):
    def test_available_reflects_key(self):
        # An explicit key (or an ambient JEV_API_KEY) makes the mapper available; with no
        # key anywhere it is not. Clear the env so a local .env / CI secret can't leak in.
        self.assertTrue(JevMapper(api_key="k").available)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JEV_API_KEY", None)
            self.assertFalse(JevMapper(api_key=None).available)

    def test_accepts_confident_typo(self):
        m = ScriptedJev({"Supressor": ("OBJID_Module::DA_Module_Ability_Atrophy.1", 0.99)})
        res = m.resolve("Supressor", CRITERIA)
        self.assertEqual(res.refs, ["OBJID_Module::DA_Module_Ability_Atrophy.1"])
        self.assertEqual(res.method, "jev")
        self.assertTrue(res.ok)

    def test_rejects_low_confidence(self):
        m = ScriptedJev({"Zorbtackle": ("OBJID_VirtualBot::phantom", 0.08)})
        res = m.resolve("Zorbtackle", CRITERIA)
        self.assertFalse(res.ok)
        self.assertEqual(res.method, "unmapped")
        self.assertEqual(res.detail["best"], "OBJID_VirtualBot::phantom")

    def test_reconstructs_mis_split(self):
        # Whole token is a low-ish single pick; each piece is a distinct confident hit.
        m = ScriptedJev({
            "Ceresm Norna": ("OBJID_VirtualBot::norna", 0.84),
            "Ceresm": ("OBJID_VirtualBot::ceres", 1.0),
            "Norna": ("OBJID_VirtualBot::norna", 1.0),
        })
        res = m.resolve("Ceresm Norna", CRITERIA)
        self.assertEqual(res.method, "jev-split")
        self.assertEqual(res.refs, ["OBJID_VirtualBot::ceres", "OBJID_VirtualBot::norna"])

    def test_never_splits_exact_vocab_two_word_name(self):
        # "Kinetic Pulse" is an exact vocab entry -> resolved whole, pieces never queried.
        m = ScriptedJev({"Kinetic Pulse": ("OBJID_Module::DA_Module_Ability_KineticPulse.1", 1.0)})
        res = m.resolve("Kinetic Pulse", CRITERIA)
        self.assertEqual(res.refs, ["OBJID_Module::DA_Module_Ability_KineticPulse.1"])
        self.assertEqual(m.calls, ["Kinetic Pulse"])  # no per-piece calls

    def test_declines_split_when_pieces_collapse(self):
        # Typo of a genuine two-word name: pieces map to the SAME ref -> keep whole.
        m = ScriptedJev({
            "Ghst Turret": ("OBJID_Module::DA_Module_Ability_GhostTurret.1", 1.0),
            "Ghst": ("OBJID_Module::DA_Module_Ability_GhostTurret.1", 0.9),
            "Turret": ("OBJID_Module::DA_Module_Ability_GhostTurret.1", 0.88),
        })
        res = m.resolve("Ghst Turret", CRITERIA)
        self.assertEqual(res.method, "jev")
        self.assertEqual(res.refs, ["OBJID_Module::DA_Module_Ability_GhostTurret.1"])


class FakeMapper:
    """Minimal stand-in for perform_mapping: returns scripted Resolutions."""

    available = True

    def __init__(self, table):
        self.table = table

    def resolve(self, name, criteria):
        return self.table[name]

    def close(self):
        pass


class TestPerformMappingWithJev(unittest.TestCase):
    def test_manual_override_takes_precedence_and_supports_lists(self):
        manual = {"Ceresm Norna": ["OBJID_VirtualBot::ceres", "OBJID_VirtualBot::norna"]}
        mapper = FakeMapper({})  # resolve() must never be called
        refs, updated, new = perform_mapping(["Ceresm Norna"], GAME_DATA, manual, mapper=mapper)
        self.assertEqual(refs, ["OBJID_VirtualBot::ceres", "OBJID_VirtualBot::norna"])
        self.assertFalse(new)

    def test_jev_hit_recorded_to_manual_mapping(self):
        mapper = FakeMapper({
            "Orkans": Resolution("Orkans", ["OBJID_Module::DA_Module_Weapon_Orkan.0"], 0.99, "jev"),
        })
        refs, updated, new = perform_mapping(["Orkans"], GAME_DATA, {}, mapper=mapper)
        self.assertEqual(refs, ["OBJID_Module::DA_Module_Weapon_Orkan.0"])
        self.assertTrue(new)
        self.assertEqual(updated["Orkans"], "OBJID_Module::DA_Module_Weapon_Orkan.0")

    def test_jev_split_recorded_as_list(self):
        mapper = FakeMapper({
            "Ceresm Norna": Resolution(
                "Ceresm Norna",
                ["OBJID_VirtualBot::ceres", "OBJID_VirtualBot::norna"],
                0.95, "jev-split",
            ),
        })
        refs, updated, new = perform_mapping(["Ceresm Norna"], GAME_DATA, {}, mapper=mapper)
        self.assertEqual(refs, ["OBJID_VirtualBot::ceres", "OBJID_VirtualBot::norna"])
        self.assertEqual(updated["Ceresm Norna"], ["OBJID_VirtualBot::ceres", "OBJID_VirtualBot::norna"])

    def test_unresolved_item_raises(self):
        mapper = FakeMapper({
            "Zorbtackle": Resolution("Zorbtackle", [], 0.08, "unmapped",
                                     {"best": "OBJID_VirtualBot::phantom"}),
        })
        with self.assertRaises(ValueError) as ctx:
            perform_mapping(["Zorbtackle"], GAME_DATA, {}, mapper=mapper)
        self.assertIn("Zorbtackle", str(ctx.exception))

    def test_exact_and_manual_resolve_without_calling_jev(self):
        # Exact vocab name + manual pin should both skip Jev entirely.
        mapper = FakeMapper({})  # any resolve() call would KeyError
        refs, _, new = perform_mapping(["Phantom"], GAME_DATA, {}, mapper=mapper)
        self.assertEqual(refs, ["OBJID_VirtualBot::phantom"])
        self.assertFalse(new)


if __name__ == "__main__":
    unittest.main()
