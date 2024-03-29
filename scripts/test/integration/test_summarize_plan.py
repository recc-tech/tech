import inspect
import json
import unittest
from datetime import date
from pathlib import Path
from typing import Dict
from unittest.mock import create_autospec

from args import ReccArgs
from autochecklist import Messenger
from config import Config
from external_services import CredentialStore, Plan, PlanningCenterClient, Song
from lib import PlanItemsSummary, get_plan_summary

_DATA_DIR = Path(__file__).parent.joinpath("summarize_plan_data")
_PLANS_URL = (
    "https://api.planningcenteronline.com/services/v2/service_types/882857/plans"
)
_PLAN_ITEMS_20240225_URL = "https://api.planningcenteronline.com/services/v2/service_types/882857/plans/69868600/items"
_PARAMS_20240225_PLANS = {
    "filter": "before,after",
    "before": "2024-02-26",
    "after": "2024-02-25",
}
_PARAMS_20240225_PLAN_ITEMS = {"per_page": 200, "include": "song"}
_PLAN_ITEMS_20240317_URL = "https://api.planningcenteronline.com/services/v2/service_types/882857/plans/70722878/items"
_PARAMS_20240317_PLANS = {
    "filter": "before,after",
    "before": "2024-03-18",
    "after": "2024-03-17",
}
_PARAMS_20240317_PLAN_ITEMS = {"per_page": 200, "include": "song"}


def _get_canned_response(fname: str) -> Dict[str, object]:
    with open(_DATA_DIR.joinpath(fname), "r", encoding="utf-8") as f:
        return json.load(f)


def get_canned_response(url: str, params: Dict[str, object]) -> Dict[str, object]:
    if url == _PLANS_URL and params == _PARAMS_20240225_PLANS:
        return _get_canned_response("20240225_plan.json")
    if url == _PLAN_ITEMS_20240225_URL and params == _PARAMS_20240225_PLAN_ITEMS:
        return _get_canned_response("20240225_plan_items.json")
    if url == _PLANS_URL and params == _PARAMS_20240317_PLANS:
        return _get_canned_response("20240317_plan.json")
    if url == _PLAN_ITEMS_20240317_URL and params == _PARAMS_20240317_PLAN_ITEMS:
        return _get_canned_response("20240317_plan_items.json")
    raise ValueError(f"Unrecognized request (url: '{url}', params: {params})")


class SummarizePlanTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def test_summarize_20240225(self) -> None:
        config = Config(
            args=ReccArgs.parse([]),
            profile="foh_dev",
            allow_multiple_only_for_testing=True,
        )
        credential_store = create_autospec(CredentialStore)
        messenger = create_autospec(Messenger)
        pco_client = PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            lazy_login=True,
        )
        pco_client._send_and_check_status = (  # pyright: ignore[reportPrivateUsage]
            get_canned_response
        )
        dt = date(year=2024, month=2, day=25)

        expected_summary = PlanItemsSummary(
            plan=Plan(
                id="69868600",
                series_title="Save The Date",
                title="Disappointed Yet Deeply Hopeful",
                date=dt,
            ),
            walk_in_slides=[
                "River’s Edge Community Church",
                "Belong Before You Believe",
                "Save The Date Series Title Slide",
                "Ways To Give",
                "The After party",
                "RE Website",
                "Follow Us Instagram",
            ],
            opener_video="Relationship Goals Intro Video",
            announcements=[
                "Thanks For Joining Us",
                "Belong Before You Believe",
                "Message Series - Title Slide",
                "Worship & Prayer Room",
                "Pulse Retreat",
                "Community Hall Fundraiser",
                "Ways To Give",
                "Prayer Ministry",
                "Website",
                "After Party",
                "See You Next Sunday",
            ],
            # TODO
            songs=[
                Song(
                    ccli=None,
                    title="You Are Mine (E)",
                    author=None,
                ),
                Song(
                    ccli=None,
                    title="Worthy of it All / I Exalt Thee (B)",
                    author=None,
                ),
                Song(
                    ccli=None,
                    title="Better is One Day (C)",
                    author=None,
                ),
                Song(
                    ccli=None,
                    title="Same God (D)",
                    author=None,
                ),
            ],
            bumper_video="Save The Date Bumper Video",
            message_notes=inspect.cleandoc(
                """Disappointed Yet Deeply Hopeful 
                God’s Heart Is That You Find The One & That It Lasts Matthew 19:4-6 NIV
                God’s Gives Us Wisdom In Avoiding Disappointment
                Proverbs 27:12 NLT
                How do I find the right person?
                How do I become the right person?
                How you see marriage shapes how you approach relationships. 
                You don’t attract what you want; you attract what you are.
                Proverbs 27:19 NLT
                Clear Signs To Avoid The Wrong Person & Being The Wrong Person
                When they’re not consistently pursuing Jesus.
                People talk about and live out what they value most.
                2 Corinthians 6:14-15 NIV 
                Amos 3:3 NLT
                Why You Settle & Accept Less Than You Deserve
                Proverbs 27:7 NLT 
                Don’t give them your heart if God doesn’t have theirs.
                When those you love don’t love who you’re dating. 
                Proverbs 27:9 NLT
                Proverbs 12:15 NLT
                When you don’t experience healthy conflict.
                James 1:19-20 NIV 
                Proverbs 27:14-16 NLT
                When you find it difficult to trust the one you’re with.
                1 Corinthians 13:7 NIV
                Proverbs 27:8 NLT
                Proverbs 5:15-17 NLT
                When they’re leading you away from Jesus instead of closer to Jesus.
                Matthew 24:4 NLT
                Psalm 119:115 NLT"""
            ),
        )
        actual_summary = get_plan_summary(client=pco_client, messenger=messenger, dt=dt)

        # Compare field-by-field for better error message
        self.assertEqual(expected_summary.plan, actual_summary.plan)
        self.assertEqual(expected_summary.walk_in_slides, actual_summary.walk_in_slides)
        self.assertEqual(expected_summary.opener_video, actual_summary.opener_video)
        self.assertEqual(expected_summary.announcements, actual_summary.announcements)
        self.assertEqual(expected_summary.songs, actual_summary.songs)
        self.assertEqual(expected_summary.bumper_video, actual_summary.bumper_video)
        self.assertEqual(expected_summary.message_notes, actual_summary.message_notes)
        # Just in case
        self.assertEqual(expected_summary, actual_summary)
        messenger.log_problem.assert_not_called()

    def test_summarize_20240317(self) -> None:
        config = Config(
            args=ReccArgs.parse([]),
            profile="foh_dev",
            allow_multiple_only_for_testing=True,
        )
        credential_store = create_autospec(CredentialStore)
        messenger = create_autospec(Messenger)
        pco_client = PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            lazy_login=True,
        )
        pco_client._send_and_check_status = (  # pyright: ignore[reportPrivateUsage]
            get_canned_response
        )
        dt = date(year=2024, month=3, day=17)

        expected_summary = PlanItemsSummary(
            plan=Plan(
                id="70722878",
                series_title="The Walk To The Cross",
                title="Crowned",
                date=dt,
            ),
            walk_in_slides=[
                "River’s Edge Community Church",
                "Belong Before You Believe",
                "The Way Of The Cross Series Title Slide",
                "Ways To Give",
                "The After party",
                "RE Website",
                "Follow Us Instagram",
            ],
            opener_video="Worship Intro Video",
            announcements=[
                "Thanks For Joining Us",
                "Belong Before You Believe",
                "Message Series - Title Slide",
                "AGM",
                "Cafe Volunteers",
                "Community Kitchen Brunch",
                "Pulse Retreat",
                "Community Hall Fundraiser",
                "4 Ways To Give",
                "Prayer Ministry",
                "Website",
                "After Party",
                "See You Next Sunday",
            ],
            songs=[
                Song(
                    ccli="7138371",
                    title="Everlasting Light",
                    author="Bede Benjamin-Korporaal, Jessie Early, and Mariah Gross",
                ),
                Song(
                    ccli="2456623",
                    title="You Are My King (Amazing Love)",
                    author="Billy Foote",
                ),
                Song(
                    ccli="6454621",
                    title="Victor's Crown",
                    author="Israel Houghton, Kari Jobe, and Darlene Zschech",
                ),
                Song(
                    ccli="6219086",
                    title="Redeemed",
                    author="Michael Weaver and Benji Cowart",
                ),
            ],
            bumper_video="24 Hours That Changed Everything",
            message_notes=inspect.cleandoc(
                """Crowned
                Mark 14:61-65 NLT
                John 18:35-37 NLT
                A Twisted Truth
                John 19:2 NLT
                A Twisted Pain
                Proverbs 22:5 NLT
                A Twisted Crown
                Genesis 3:17-18 NLT
                A Twisted Curse
                Hebrews 12:2-3 NLT
                A Crowned King"""
            ),
        )
        actual_summary = get_plan_summary(client=pco_client, messenger=messenger, dt=dt)

        # Compare field-by-field for better error message
        self.assertEqual(expected_summary.plan, actual_summary.plan)
        self.assertEqual(expected_summary.walk_in_slides, actual_summary.walk_in_slides)
        self.assertEqual(expected_summary.opener_video, actual_summary.opener_video)
        self.assertEqual(expected_summary.announcements, actual_summary.announcements)
        self.assertEqual(expected_summary.songs, actual_summary.songs)
        self.assertEqual(expected_summary.bumper_video, actual_summary.bumper_video)
        self.assertEqual(expected_summary.message_notes, actual_summary.message_notes)
        # Just in case
        self.assertEqual(expected_summary, actual_summary)
        messenger.log_problem.assert_not_called()
