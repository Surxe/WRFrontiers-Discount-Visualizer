import copy
import json
import os
import sys
import unittest
from unittest import mock

import requests

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

import config
import discord_event
from discord_event import (
    DiscordEventError,
    event_to_announcement,
    event_to_date_range,
    fetch_event,
)
from run import resolve_inputs


EVENT_ID = "1568259964999565422"
FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', f'discord_event_{EVENT_ID}.json')
with open(FIXTURE, encoding='utf-8') as f:
    PAYLOAD = json.load(f)

EXPECTED_ITEMS = (
    "Heike, Orochi, Varangian, Thunder, Zeus, Orkan, Apollo, "
    "Blast Wave, Recon Mode, Fuel Burn, Flashbang, Ghost Turret, Gamma Beam"
)


def _response(payload, status=200):
    resp = mock.Mock()
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status} Error")
    else:
        resp.raise_for_status.return_value = None
    return resp


def _get_returning(payload, status=200):
    return mock.patch.object(discord_event.requests, 'get', return_value=_response(payload, status))


class TestFetchEvent(unittest.TestCase):

    def test_happy_path(self):
        with _get_returning(PAYLOAD) as get:
            event = fetch_event(EVENT_ID)
        self.assertEqual(event["id"], EVENT_ID)
        args, kwargs = get.call_args
        self.assertEqual(args[0], f"{config.DISCORD_API_BASE}/invites/{config.DISCORD_INVITE_CODE}")
        self.assertEqual(kwargs["params"], {"guild_scheduled_event_id": EVENT_ID})
        self.assertIn("timeout", kwargs)

    def test_event_missing_from_response(self):
        payload = {k: v for k, v in PAYLOAD.items() if k != "guild_scheduled_event"}
        with _get_returning(payload):
            with self.assertRaisesRegex(DiscordEventError, "not found"):
                fetch_event(EVENT_ID)

    def test_guild_id_mismatch(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["guild_id"] = payload["guild_scheduled_event"]["guild_id"] = "123456789012345678"
        with _get_returning(payload):
            with self.assertRaisesRegex(DiscordEventError, "guild"):
                fetch_event(EVENT_ID)

    def test_http_error(self):
        with _get_returning({}, status=404):
            with self.assertRaisesRegex(DiscordEventError, "Could not fetch"):
                fetch_event(EVENT_ID)

    def test_non_snowflake_rejected_without_request(self):
        with _get_returning(PAYLOAD) as get:
            for bad in ("", "abc", "12345", "https://discord.com/events/941368722860417105/1568259964999565422"):
                with self.assertRaises(DiscordEventError):
                    fetch_event(bad)
        get.assert_not_called()


class TestEventFields(unittest.TestCase):

    def test_announcement_parses_to_items(self):
        from announcement import announcement_to_items
        text = event_to_announcement(PAYLOAD["guild_scheduled_event"])
        self.assertEqual(announcement_to_items(text), EXPECTED_ITEMS)

    def test_date_range_from_fixture(self):
        self.assertEqual(event_to_date_range(PAYLOAD["guild_scheduled_event"]), "11-10 11-17")

    def test_date_range_uses_utc(self):
        event = {
            "scheduled_start_time": "2026-12-29T01:00:00-08:00",  # 09:00Z Dec 29
            "scheduled_end_time": "2027-01-04T23:30:00-08:00",    # 07:30Z Jan 5
        }
        self.assertEqual(event_to_date_range(event), "12-29 01-05")

    def test_missing_times_raise(self):
        with self.assertRaises(DiscordEventError):
            event_to_date_range({"scheduled_start_time": "2026-11-10T10:00:00+00:00"})


class TestResolveInputs(unittest.TestCase):

    def setUp(self):
        self.logger = mock.Mock()

    def test_items_only(self):
        self.assertEqual(
            resolve_inputs("Phantom, Blink", "", "06-16 06-23", self.logger),
            ("Phantom, Blink", "06-16 06-23"),
        )

    def test_items_need_date_range(self):
        with self.assertRaisesRegex(ValueError, "--date-range"):
            resolve_inputs("Phantom", "", "", self.logger)

    def test_exactly_one_source(self):
        for items, event_id in (("", ""), ("Phantom", EVENT_ID), ("  ", " ")):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                resolve_inputs(items, event_id, "06-16 06-23", self.logger)

    def test_event_defaults_date_range(self):
        with _get_returning(PAYLOAD):
            self.assertEqual(
                resolve_inputs("", EVENT_ID, "", self.logger),
                (EXPECTED_ITEMS, "11-10 11-17"),
            )
        self.logger.warning.assert_not_called()

    def test_explicit_date_range_wins_and_warns(self):
        with _get_returning(PAYLOAD):
            _, date_range = resolve_inputs("", EVENT_ID, "11-11 11-18", self.logger)
        self.assertEqual(date_range, "11-11 11-18")
        self.logger.warning.assert_called_once()

    def test_matching_date_range_does_not_warn(self):
        with _get_returning(PAYLOAD):
            resolve_inputs("", EVENT_ID, "11-10 11-17", self.logger)
        self.logger.warning.assert_not_called()


if __name__ == '__main__':
    unittest.main()
