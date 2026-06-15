import unittest
import sys
import os

# Add src/backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from step2_map_items import perform_mapping

class TestFuzzyMapping(unittest.TestCase):
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
        """Test that exact matches (case-insensitive) are mapped correctly without new mappings flagged."""
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

    def test_fuzzy_matches_real_typos(self):
        """Test fuzzy mapping with realistic typos / variations."""
        # "Phantm" -> "Phantom"
        # "Varangn" -> "Varangian"
        # "Emergancy Shield" -> "Emergency Shield"
        # "Ammo Fabricatr" -> "Ammo Fabricator"
        items = ["Phantm", "Varangn", "Emergancy Shield", "Ammo Fabricatr"]
        mapped_refs, updated_manual_mapping, new_mappings_found = perform_mapping(
            items, self.game_data, self.manual_mapping
        )
        
        expected_refs = [
            "OBJID_VirtualBot::phantom",
            "OBJID_VirtualBot::varangian",
            "OBJID_Module::DA_Module_Ability_ArmorShield.1",
            "OBJID_Module::DA_Module_Ability_AmmoGenerator.1"
        ]
        self.assertEqual(mapped_refs, expected_refs)
        self.assertTrue(new_mappings_found)
        self.assertEqual(updated_manual_mapping, {
            "Phantm": "OBJID_VirtualBot::phantom",
            "Varangn": "OBJID_VirtualBot::varangian",
            "Emergancy Shield": "OBJID_Module::DA_Module_Ability_ArmorShield.1",
            "Ammo Fabricatr": "OBJID_Module::DA_Module_Ability_AmmoGenerator.1"
        })

    def test_respect_existing_manual_mappings(self):
        """Test that existing manual mappings are respected and do not trigger 'new mappings' flag."""
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

    def test_unmappable_item_errors(self):
        """Test that an error (ValueError) is raised if an item cannot be mapped (no close match)."""
        items = ["NonExistentItemXYZ"]
        with self.assertRaises(ValueError) as context:
            perform_mapping(items, self.game_data, self.manual_mapping)
        
        self.assertIn("Unable to map the following items", str(context.exception))
        self.assertIn("NonExistentItemXYZ", str(context.exception))

if __name__ == '__main__':
    unittest.main()
