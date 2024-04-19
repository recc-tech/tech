import inspect
import json
import unittest
from datetime import date
from pathlib import Path
from typing import Dict
from unittest.mock import call, create_autospec

from args import ReccArgs
from autochecklist import Messenger, ProblemLevel
from config import Config
from external_services import (
    CredentialStore,
    ItemNote,
    Plan,
    PlanningCenterClient,
    Song,
)
from lib import AnnotatedSong, PlanItemsSummary, get_plan_summary

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
_PARAMS_20240225_PLAN_ITEMS = {"per_page": 200, "include": "song,item_notes"}
_PLAN_ITEMS_20240414_URL = "https://api.planningcenteronline.com/services/v2/service_types/882857/plans/71699950/items"
_PARAMS_20240414_PLANS = {
    "filter": "before,after",
    "before": "2024-04-15",
    "after": "2024-04-14",
}
_PARAMS_20240414_PLAN_ITEMS = {"per_page": 200, "include": "song,item_notes"}


def _get_canned_response(fname: str) -> Dict[str, object]:
    with open(_DATA_DIR.joinpath(fname), "r", encoding="utf-8") as f:
        return json.load(f)


def get_canned_response(url: str, params: Dict[str, object]) -> Dict[str, object]:
    if url == _PLANS_URL and params == _PARAMS_20240225_PLANS:
        return _get_canned_response("20240225_plan.json")
    if url == _PLAN_ITEMS_20240225_URL and params == _PARAMS_20240225_PLAN_ITEMS:
        return _get_canned_response("20240225_plan_items.json")
    if url == _PLANS_URL and params == _PARAMS_20240414_PLANS:
        return _get_canned_response("20240414_plan.json")
    if url == _PLAN_ITEMS_20240414_URL and params == _PARAMS_20240414_PLAN_ITEMS:
        return _get_canned_response("20240414_plan_items.json")
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
            announcements_video=None,
            songs=[
                AnnotatedSong(
                    Song(
                        ccli=None,
                        title="You Are Mine (E)",
                        author=None,
                    ),
                    [
                        ItemNote(
                            category="Visuals",
                            contents="Please show at the beginning\nIris will welcome, read these bible verses & pray. \nVerses: \n--\n”Why, my soul, are you downcast? Why so disturbed within me? Put your hope in God, for I will yet praise him, my Saviour and my God. My soul is downcast within me; therefore I will remember you from the land of the Jordan, the heights of Hermon—from Mount Mizar. Deep calls to deep in the roar of your waterfalls; all your waves and breakers have swept over me. By day the Lord directs his love, at night his song is with me— a prayer to the God of my life.\n\u202d\u202dPsalms\u202c \u202d42\u202c:\u202d5\u202c-8 \u202dNIV\u202c\u202c",
                        )
                    ],
                ),
                AnnotatedSong(
                    Song(
                        ccli=None,
                        title="Worthy of it All / I Exalt Thee (B)",
                        author=None,
                    ),
                    [
                        ItemNote(
                            category="Visuals",
                            contents="During the instrumental before the bridge:\n”May my prayer be set before you like incense; may the lifting up of my hands be like the evening sacrifice.“\n\u202d\u202dPsalms\u202c \u202d141\u202c:\u202d2\u202c \u202dNIV\u202c\u202c",
                        )
                    ],
                ),
                AnnotatedSong(
                    Song(
                        ccli=None,
                        title="Better is One Day (C)",
                        author=None,
                    ),
                    [],
                ),
                AnnotatedSong(
                    Song(
                        ccli=None,
                        title="Same God (D)",
                        author=None,
                    ),
                    [
                        ItemNote(
                            category="Visuals",
                            contents="During the first Instrumental before the bridge:\n--\n”Jesus Christ is the same yesterday and today and forever.“\n\u202d\u202dHebrews\u202c \u202d13\u202c:\u202d8\u202c \u202dNIV",
                        )
                    ],
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
        messenger.log_problem.assert_has_calls(
            [
                call(level=ProblemLevel.WARN, message="No announcements video found."),
                call(
                    level=ProblemLevel.WARN,
                    message="Found 4 items that look like songs.",
                ),
            ]
        )
        self.assertEqual(2, messenger.log_problem.call_count)

    def test_summarize_20240414(self) -> None:
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
        dt = date(year=2024, month=4, day=14)

        expected_summary = PlanItemsSummary(
            plan=Plan(
                id="71699950",
                series_title="WORTHY",
                title="Worthy Of The Feast",
                date=dt,
            ),
            walk_in_slides=[
                "River’s Edge",
                "Faith - Love - Hope",
                "Worthy Series Title Slide",
                "Give Generously",
                "The After Party",
                "Website",
                "Follow Us Instagram",
            ],
            opener_video="Welcome Opener Video",
            announcements=[
                "PIANO playing In the Background",
                "WELCOME",
                "PRAY For People",
                "CONTINUE To Worship",
                "GIVING TALK",
                "Prayer Ministry",
                "After Party",
                "See You Next Sunday",
            ],
            announcements_video="Video Announcements",
            songs=[
                AnnotatedSong(
                    Song(
                        ccli="7104200",
                        title="Echo",
                        author="Israel Houghton, Matthew Ntlele, Chris Brown, Steven Furtick, and Alexander Pappas",
                    ),
                    [],
                ),
                # Linked song, but no CCLI number or author
                AnnotatedSong(
                    Song(
                        ccli=None,
                        title="Different (Live at Mosaic, Los Angeles, 2023)",
                        author=None,
                    ),
                    [],
                ),
                AnnotatedSong(
                    Song(
                        ccli="5508444",
                        title="One Thing Remains",
                        author="Christa Black, Brian Johnson, and Jeremy Riddle",
                    ),
                    [
                        ItemNote(
                            category="Visuals",
                            contents="Add lyrics at the end:\n\nBless the Lord, oh my soul\nEverything within me give Him praise (4x)\n\nYou’re just so good (3x)\n",
                        )
                    ],
                ),
                AnnotatedSong(
                    Song(
                        ccli="7117726",
                        title="Goodness Of God",
                        author="Ed Cash and Jenn Johnson",
                    ),
                    [
                        ItemNote(
                            category="Visuals",
                            contents='Extended version: At the end will add the Chorus of another song called Evidence by Josh Baldwin:               "I see the evidence of your goodness. All over my life. All over life. I see your promises in fulfillment. All over my life. All over my life."                                            \n Repeated several times. The will go back to the Bridges and Chorus and then end the song. ',
                        )
                    ],
                ),
                # No linked song at all
                AnnotatedSong(
                    Song(
                        ccli=None,
                        title="Song 5: DIFFERENT ",
                        author=None,
                    ),
                    [],
                ),
            ],
            bumper_video="Worthy Sermon Bumper Video",
            message_notes=inspect.cleandoc(
                """Worthy Of The Feast
                Matthew 22:1-14 NLT
                Our Worth Isn’t Earned It’s Given
                Matthew 22:4
                Our Worth Is Experienced Through Acceptance
                Matthew 22:10
                Our Worth Is Revealed By Our Garments
                Matthew 22:11
                You Are Worthy Because You Are Chosen
                Matthew 22:14
                Our Worth Is Connected To Our Embrace Of The Worth Of The Feast
                Live According To The Level Of Worth We Have Received"""
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
