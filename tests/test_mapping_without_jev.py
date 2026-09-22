import unittest
import sys
import os

# Add src/backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from step2_map_items import perform_mapping


class TestMappingWithoutJev(unittest.TestCase):
    """perform_mapping with no mapper (no JEV_API_KEY): only manual pins and exact
    vocab matches resolve; anything else is raised as an error. Jev-backed resolution
    is covered in test_jev_mapping.py."""

    def setUp(self):
        # A mock subset of game_data representing real objects from current game_data.json
        self.game_data = [
            {"ref": "OBJID_VirtualBot::phantom", "name": "Phantom"},
            {"ref": "OBJID_VirtualBot::varangian", "name": "Varangian"},
            {"ref": "OBJID_Module::DA_Module_Weapon_Zeus.0", "name": "Zeus"},
            {"ref": "OBJID_Module::DA_Module_Weapon_Lighter.0", "name": "Lighter"},
            {"ref": "OBJID_Module::DA_Module_Ability_ArmorShield.1", "name": "Emergency Shield"},
            {"ref": "OBJID_Module::DA_Module_Ability_AmmoGenerator.1", "name": "Ammo Fabricator"},
            {"ref": "OBJID_Module::DA_Module_Ability_DashBlinkedVisible.1", "name": "Blink"},
        ]
        self.manual_mapping = {}

    def test_exact_matches(self):
        """Exact matches (case-insensitive) are mapped correctly without new mappings flagged."""
        items = ["Phantom", "lighter", "Blink"]
        mapped_refs, updated_manual_mapping, new_mappings_found = perform_mapping(
            items, self.game_data, self.manual_mapping
        )

        self.assertEqual(mapped_refs, [
            "OBJID_VirtualBot::phantom",
            "OBJID_Module::DA_Module_Weapon_Lighter.0",
            "OBJID_Module::DA_Module_Ability_DashBlinkedVisible.1"
        ])
        self.assertFalse(new_mappings_found)
        self.assertEqual(updated_manual_mapping, {})

    def test_respect_existing_manual_mappings(self):
        """Existing manual mappings are respected and do not trigger the 'new mappings' flag."""
        manual_mapping = {
            "phtm": "OBJID_VirtualBot::phantom"
        }
        items = ["phtm"]
        mapped_refs, updated_manual_mapping, new_mappings_found = perform_mapping(
            items, self.game_data, manual_mapping
        )

        self.assertEqual(mapped_refs, ["OBJID_VirtualBot::phantom"])
        self.assertFalse(new_mappings_found)
        self.assertEqual(updated_manual_mapping, manual_mapping)

    def test_typo_without_jev_errors(self):
        """Without Jev, a near-miss typo is NOT silently resolved -- it errors out."""
        items = ["Phantm"]  # would previously fuzzy-match "Phantom"
        with self.assertRaises(ValueError) as context:
            perform_mapping(items, self.game_data, self.manual_mapping)

        self.assertIn("Unable to map the following items", str(context.exception))
        self.assertIn("Phantm", str(context.exception))

    def test_unmappable_item_errors(self):
        """An item that is neither a pin nor an exact match raises ValueError."""
        items = ["NonExistentItemXYZ"]
        with self.assertRaises(ValueError) as context:
            perform_mapping(items, self.game_data, self.manual_mapping)

        self.assertIn("Unable to map the following items", str(context.exception))
        self.assertIn("NonExistentItemXYZ", str(context.exception))


if __name__ == '__main__':
    unittest.main()
