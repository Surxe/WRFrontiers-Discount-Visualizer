import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from announcement import announcement_to_items, parse_announcement


LEAD = "This week, the Tortuga engineers invite Pilots to take a closer look at the following builds:"
BODY = (
    "War Robot Modules: Heike, Orochi, Varangian\n\n"
    "Weapons: Thunder, Zeus, Orkan, Apollo\n\n"
    "Gear: Blast Wave, Recon Mode, Fuel Burn, Flashbang, Ghost Turret, Gamma Beam"
)
EXPECTED = (
    "Heike, Orochi, Varangian, Thunder, Zeus, Orkan, Apollo, "
    "Blast Wave, Recon Mode, Fuel Burn, Flashbang, Ghost Turret, Gamma Beam"
)


class TestAnnouncement(unittest.TestCase):

    def test_with_lead_sentence(self):
        self.assertEqual(announcement_to_items(f"{LEAD}\n\n{BODY}"), EXPECTED)

    def test_without_lead_sentence(self):
        self.assertEqual(announcement_to_items(BODY), EXPECTED)

    def test_newlines_stripped_by_single_line_input(self):
        # A browser text input drops newlines on paste, gluing lines together.
        flat = f"{LEAD}\n\n{BODY}".replace("\n", "")
        self.assertEqual(announcement_to_items(flat), EXPECTED)

    def test_newlines_replaced_by_spaces(self):
        flat = f"{LEAD}\n\n{BODY}".replace("\n", " ")
        self.assertEqual(announcement_to_items(flat), EXPECTED)

    def test_markdown_bullets_and_bold(self):
        text = (
            f"{LEAD}\n"
            "- **War Robot Modules**: Heike, Orochi, Varangian\n"
            "- **Weapons**: Thunder, Zeus, Orkan, Apollo\n"
            "- **Gear**: Blast Wave, Recon Mode, Fuel Burn, Flashbang, Ghost Turret, Gamma Beam\n"
        )
        self.assertEqual(announcement_to_items(text), EXPECTED)

    def test_trailing_line_dropped(self):
        text = f"{BODY}\n\nSee you on the battlefield, Pilots!"
        self.assertEqual(announcement_to_items(text), EXPECTED)

    def test_missing_category_is_fine(self):
        cats = parse_announcement("Weapons: Thunder, Zeus\nGear: Flashbang")
        self.assertEqual(cats, {"Weapons": ["Thunder", "Zeus"], "Gear": ["Flashbang"]})

    def test_no_labels_raises(self):
        with self.assertRaises(ValueError):
            announcement_to_items("Heike, Orochi, Varangian")

    def test_repeated_label_raises(self):
        with self.assertRaises(ValueError):
            announcement_to_items(f"{BODY}\n\n{BODY}")


if __name__ == '__main__':
    unittest.main()
