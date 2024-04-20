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
from lib import (
    AnnotatedItem,
    AnnotatedSong,
    PlanItemsSummary,
    get_plan_summary,
    load_plan_summary,
)

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

    def test_load_summary(self) -> None:
        expected_summary = PlanItemsSummary(
            plan=Plan(
                id="71699950",
                series_title="WORTHY",
                title="Worthy Of The Feast",
                date=date(year=2024, month=4, day=14),
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
            opener_video=AnnotatedItem(content="Welcome Opener Video", notes=[]),
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
            announcements_video=AnnotatedItem(content="Video Announcements", notes=[]),
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
            bumper_video=AnnotatedItem(content="Worthy Sermon Bumper Video", notes=[]),
            message_notes=AnnotatedItem(
                content=inspect.cleandoc(
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
                    Live According To The Level Of Worth We Have Received""",
                ),
                notes=[ItemNote(category="Visuals", contents="Name slide")],
            ),
            has_visuals_notes=True,
        )
        actual_summary = load_plan_summary(_DATA_DIR.joinpath("20240414_summary.json"))
        self.assert_equal_summary(expected_summary, actual_summary)

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

        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240225_summary.json")
        )
        actual_summary = get_plan_summary(
            client=pco_client, messenger=messenger, config=config, dt=dt
        )

        self.assert_equal_summary(expected_summary, actual_summary)
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

        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240414_summary.json")
        )
        actual_summary = get_plan_summary(
            client=pco_client, messenger=messenger, config=config, dt=dt
        )

        self.assert_equal_summary(expected_summary, actual_summary)
        messenger.log_problem.assert_not_called()

    def assert_equal_summary(
        self, expected: PlanItemsSummary, actual: PlanItemsSummary
    ) -> None:
        # Compare field-by-field for better error message
        self.assertEqual(expected.plan, actual.plan)
        self.assertEqual(expected.walk_in_slides, actual.walk_in_slides)
        self.assertEqual(expected.opener_video, actual.opener_video)
        self.assertEqual(expected.announcements, actual.announcements)
        self.assertEqual(expected.songs, actual.songs)
        self.assertEqual(expected.bumper_video, actual.bumper_video)
        self.assertEqual(expected.message_notes, actual.message_notes)
        # Just in case
        self.assertEqual(expected, actual)
