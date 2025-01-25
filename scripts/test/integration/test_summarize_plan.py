import inspect
import json
import os
import unittest
from datetime import date
from pathlib import Path
from tkinter import Tk
from typing import Dict, Tuple
from unittest.mock import Mock, create_autospec

from args import ReccArgs
from autochecklist import Messenger
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
    plan_summary_to_html,
    plan_summary_to_json,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.webdriver import WebDriver

_DATA_DIR = Path(__file__).parent.joinpath("summarize_plan_data")
_TEMP_DIR = Path(__file__).parent.joinpath("summarize_plan_temp")
_PLANS_URL = (
    "https://api.planningcenteronline.com/services/v2/service_types/882857/plans"
)
_PARAMS_PLAN_ITEMS = {"per_page": 200, "include": "song,item_notes"}
_PLAN_ITEMS_20240225_URL = "https://api.planningcenteronline.com/services/v2/service_types/882857/plans/69868600/items"
_PARAMS_20240225_PLANS = {
    "filter": "before,after",
    "before": "2024-02-26",
    "after": "2024-02-25",
}
_PLAN_ITEMS_20240414_URL = "https://api.planningcenteronline.com/services/v2/service_types/882857/plans/71699950/items"
_PARAMS_20240414_PLANS = {
    "filter": "before,after",
    "before": "2024-04-15",
    "after": "2024-04-14",
}
_PLAN_ITEMS_20240505_URL = "https://api.planningcenteronline.com/services/v2/service_types/882857/plans/72395216/items"
_PARAMS_20240505_PLANS = {
    "filter": "before,after",
    "before": "2024-05-06",
    "after": "2024-05-05",
}


def _get_canned_response(fname: str) -> Dict[str, object]:
    with open(_DATA_DIR.joinpath(fname), "r", encoding="utf-8") as f:
        return json.load(f)


def get_canned_response(url: str, params: Dict[str, object]) -> Dict[str, object]:
    if url == _PLANS_URL and params == _PARAMS_20240225_PLANS:
        return _get_canned_response("20240225_plan.json")
    if url == _PLAN_ITEMS_20240225_URL and params == _PARAMS_PLAN_ITEMS:
        return _get_canned_response("20240225_plan_items.json")
    if url == _PLANS_URL and params == _PARAMS_20240414_PLANS:
        return _get_canned_response("20240414_plan.json")
    if url == _PLAN_ITEMS_20240414_URL and params == _PARAMS_PLAN_ITEMS:
        return _get_canned_response("20240414_plan_items.json")
    if url == _PLANS_URL and params == _PARAMS_20240505_PLANS:
        return _get_canned_response("20240505_plan.json")
    if url == _PLAN_ITEMS_20240505_URL and params == _PARAMS_PLAN_ITEMS:
        return _get_canned_response("20240505_plan_items.json")
    raise ValueError(f"Unrecognized request (url: '{url}', params: {params})")


class PlanSummaryTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.maxDiff = None
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)

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
        if expected.message_notes and actual.message_notes:
            self.assertEqual(
                expected.message_notes.content, actual.message_notes.content
            )
            self.assertEqual(expected.message_notes.notes, actual.message_notes.notes)
        self.assertEqual(expected.message_notes, actual.message_notes)
        # Just in case
        self.assertEqual(expected, actual)


class GeneratePlanSummaryTestCase(PlanSummaryTestCase):
    """Test `get_plan_summary()`."""

    # Not a particularly important case now that 2024-05-05 is tested, but it
    # doesn't hurt to keep it around.
    def test_summarize_20240225(self) -> None:
        (pco_client, messenger, log_problem_mock, config) = self._set_up()

        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240225_summary.json")
        )
        actual_summary = get_plan_summary(
            client=pco_client,
            messenger=messenger,
            config=config,
            dt=date(2024, 2, 25),
        )

        self.assert_equal_summary(expected_summary, actual_summary)
        log_problem_mock.assert_not_called()

    # Interesting characteristics of this test case:
    #  * CCLI provided for most, but not all songs
    #  * Plan item with no linked song
    #  * Plan item with a linked song but no CCLI number
    #  * Empty description for each song
    #  * Duplicate line in message notes (which I added for testing)
    def test_summarize_20240414(self) -> None:
        (pco_client, messenger, log_problem_mock, config) = self._set_up()

        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240414_summary.json")
        )
        actual_summary = get_plan_summary(
            client=pco_client,
            messenger=messenger,
            config=config,
            dt=date(2024, 4, 14),
        )

        self.assert_equal_summary(expected_summary, actual_summary)
        log_problem_mock.assert_not_called()

    # Interesting characteristics of this test case:
    #  * CCLI number in the description of each song
    def test_summarize_20240505(self) -> None:
        (pco_client, messenger, log_problem_mock, config) = self._set_up()

        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240505_summary.json")
        )
        actual_summary = get_plan_summary(
            client=pco_client,
            messenger=messenger,
            config=config,
            dt=date(2024, 5, 5),
        )

        self.assert_equal_summary(expected_summary, actual_summary)
        log_problem_mock.assert_not_called()

    def _set_up(self) -> Tuple[PlanningCenterClient, Messenger, Mock, Config]:
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
        return (pco_client, messenger, messenger.log_problem, config)


class PlanSummaryToHtmlTestCase(unittest.TestCase):
    """Test `plan_summary_to_html()`."""

    def setUp(self) -> None:
        self.maxDiff = None

    def test_copy_message_notes(self) -> None:
        """
        Test that the message notes can be copied from the HTML summary.
        """
        summary = load_plan_summary(_DATA_DIR.joinpath("20240414_summary.json"))
        summary_html = plan_summary_to_html(summary)
        f = _TEMP_DIR.joinpath("summary.html")
        f.write_text(summary_html, encoding="utf-8")

        # NOTE: Copying doesn't work in headless mode for some reason
        service = Service(log_path=os.devnull)
        with WebDriver(service=service) as driver:
            driver.get(f.resolve().as_uri())
            btn = driver.find_element(By.XPATH, "//button[contains(., 'Copy')]")
            btn.click()

        expected_text = inspect.cleandoc(
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
            Our worth is experienced  through[TAB]acceptance  
            Live According To The Level Of Worth We Have Received"""
        ).replace("[TAB]", "\t")
        # inspect.cleandoc replaces tabs with spaces
        self.assertEqual(expected_text, _get_clipboard_text())


class PlanSummaryJsonTestCase(PlanSummaryTestCase):
    SUMMARY = PlanItemsSummary(
        plan=Plan(
            id="71699950",
            series_title="WORTHY",
            title="Worthy Of The Feast",
            date=date(year=2024, month=4, day=14),
            web_page_url="https://services.planningcenteronline.com/plans/71699950",
        ),
        walk_in_slides=[
            "River’s Edge",
            "Worthy Series Title Slide",
            "Give Generously",
            "The After Party",
            "Website",
            "Follow Us Instagram",
        ],
        opener_video=AnnotatedItem(content="Welcome Opener Video", notes=[]),
        announcements=[
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
                notes=[],
                description="",
            ),
            # Linked song, but no CCLI number or author
            AnnotatedSong(
                Song(
                    ccli=None,
                    title="Different (Live at Mosaic, Los Angeles, 2023)",
                    author=None,
                ),
                notes=[],
                description="",
            ),
            AnnotatedSong(
                Song(
                    ccli="5508444",
                    title="One Thing Remains",
                    author="Christa Black, Brian Johnson, and Jeremy Riddle",
                ),
                notes=[
                    ItemNote(
                        category="Visuals",
                        contents="Add lyrics at the end:\n\nBless the Lord, oh my soul\nEverything within me give Him praise (4x)\n\nYou’re just so good (3x)\n",
                    )
                ],
                description="",
            ),
            AnnotatedSong(
                Song(
                    ccli="7117726",
                    title="Goodness Of God",
                    author="Ed Cash and Jenn Johnson",
                ),
                notes=[
                    ItemNote(
                        category="Visuals",
                        contents='Extended version: At the end will add the Chorus of another song called Evidence by Josh Baldwin:               "I see the evidence of your goodness. All over my life. All over life. I see your promises in fulfillment. All over my life. All over my life."                                            \n Repeated several times. The will go back to the Bridges and Chorus and then end the song. ',
                    )
                ],
                description="",
            ),
            # No linked song at all
            AnnotatedSong(
                Song(
                    ccli=None,
                    title="Song 5: DIFFERENT ",
                    author=None,
                ),
                notes=[],
                description="",
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
                Our worth is experienced  through[TAB]acceptance  
                Live According To The Level Of Worth We Have Received""",
            )
            # inspect.cleandoc expands tabs :(
            .replace("[TAB]", "\t"),
            notes=[
                ItemNote(
                    category="Warning",
                    contents='There are duplicate lines in the sermon notes ("our worth is experienced through acceptance"). Check with Pastor Lorenzo that this is intentional.',
                )
            ],
        ),
        num_visuals_notes=2,
    )

    def test_load_summary(self) -> None:
        actual_summary = load_plan_summary(_DATA_DIR.joinpath("20240414_summary.json"))
        self.assert_equal_summary(self.SUMMARY, actual_summary)

    def test_load_and_save_json_summary(self) -> None:
        n = 0
        for p in _DATA_DIR.glob("*_summary.json"):
            with self.subTest(p.stem):
                summary1 = load_plan_summary(p)
                temp_file = _TEMP_DIR.joinpath(p.relative_to(_DATA_DIR))
                temp_file.write_text(plan_summary_to_json(summary1))
                summary2 = load_plan_summary(temp_file)
                self.assert_equal_summary(summary1, summary2)
        n += 1
        # At least one test must have run, otherwise there's something wrong
        # with the test itself
        self.assertGreater(n, 0)


def _get_clipboard_text() -> str:
    root = Tk()
    x = root.clipboard_get()
    root.quit()
    return x
