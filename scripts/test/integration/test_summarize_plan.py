import inspect
import json
import os
import unittest
from datetime import date
from pathlib import Path
from tkinter import Tk
from typing import Any, Dict, Tuple
from unittest.mock import create_autospec

from args import ReccArgs
from autochecklist import Messenger
from config import Config
from external_services import (
    CredentialStore,
    ItemNote,
    Plan,
    PlanId,
    PlanningCenterClient,
    Song,
)
from lib import (
    AnnotatedItem,
    AnnotatedSong,
    Deletion,
    Insertion,
    NoOp,
    PlanSummary,
    PlanSummaryDiff,
    diff_plan_summaries,
    get_plan_summary,
    get_vocals_notes,
    load_plan_summary,
    plan_summary_diff_to_html,
    plan_summary_to_json,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.webdriver import WebDriver

_DATA_DIR = Path(__file__).parent.joinpath("summarize_plan_data")
_TEMP_DIR = Path(__file__).parent.joinpath("summarize_plan_temp")
_SERVICE_TYPES_URL = "https://api.planningcenteronline.com/services/v2/service_types"
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
_PLAN_ITEMS_20250418_URL = "https://api.planningcenteronline.com/services/v2/service_types/1237521/plans/79927548/items"


def _get_canned_response(fname: str) -> Dict[str, object]:
    with open(_DATA_DIR.joinpath(fname), "r", encoding="utf-8") as f:
        return json.load(f)


def get_canned_response(url: str, params: Dict[str, object]) -> Dict[str, object]:
    if url == _SERVICE_TYPES_URL and params == {}:
        return _get_canned_response("service_types.json")
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
    if url == _PLAN_ITEMS_20250418_URL and params == _PARAMS_PLAN_ITEMS:
        return _get_canned_response("20250418_plan_items.json")
    raise ValueError(f"Unrecognized request (url: '{url}', params: {params})")


class PlanSummaryTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.maxDiff = None
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def assert_equal_summary(self, expected: PlanSummary, actual: PlanSummary) -> None:
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
        self.assertEqual(expected.num_visuals_notes, actual.num_visuals_notes)
        # Just in case
        self.assertEqual(expected, actual)

    def assert_equal_summary_diff(
        self, expected: PlanSummaryDiff, actual: PlanSummaryDiff
    ) -> None:
        # Compare field-by-field for better error message
        self.assertEqual(expected.plan, actual.plan)
        self.assertEqual(expected.walk_in_slides, actual.walk_in_slides)
        self.assertEqual(expected.opener_video, actual.opener_video)
        self.assertEqual(expected.announcements, actual.announcements)
        self.assertEqual(expected.songs, actual.songs)
        self.assertEqual(expected.bumper_video, actual.bumper_video)
        self.assertEqual(expected.message, actual.message)
        self.assertEqual(expected.message_warnings, actual.message_warnings)
        self.assertEqual(expected.num_visuals_notes, actual.num_visuals_notes)
        # Just in case
        self.assertEqual(expected, actual)

    def create_services(self) -> Tuple[Config, Messenger, Any, PlanningCenterClient]:
        config = Config(
            args=ReccArgs.parse([]),
            profile="foh_dev",
            allow_multiple_only_for_testing=True,
        )
        credential_store = create_autospec(CredentialStore)
        messenger = create_autospec(Messenger)
        log_problem_mock = messenger.log_problem
        pco_client = PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            lazy_login=True,
        )
        pco_client._send_and_check_status = (  # pyright: ignore[reportPrivateUsage]
            get_canned_response
        )
        return (config, messenger, log_problem_mock, pco_client)


class GeneratePlanSummaryTestCase(PlanSummaryTestCase):
    """Test `get_plan_summary()`."""

    def setUp(self):
        super().setUp()
        (
            self._config,
            self._messenger,
            self._log_problem_mock,
            self._pco_client,
        ) = self.create_services()

    # Not a particularly important case now that 2024-05-05 is tested, but it
    # doesn't hurt to keep it around.
    def test_summarize_20240225(self) -> None:
        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240225_summary.json")
        )
        actual_summary = get_plan_summary(
            client=self._pco_client,
            messenger=self._messenger,
            config=self._config,
            dt=date(2024, 2, 25),
        )

        self.assert_equal_summary(expected_summary, actual_summary)
        self._log_problem_mock.assert_not_called()

    # Interesting characteristics of this test case:
    #  * CCLI provided for most, but not all songs
    #  * Plan item with no linked song
    #  * Plan item with a linked song but no CCLI number
    #  * Empty description for each song
    #  * Duplicate line in message notes (which I added for testing)
    def test_summarize_20240414(self) -> None:
        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240414_summary.json")
        )
        actual_summary = get_plan_summary(
            client=self._pco_client,
            messenger=self._messenger,
            config=self._config,
            dt=date(2024, 4, 14),
        )

        self.assert_equal_summary(expected_summary, actual_summary)
        self._log_problem_mock.assert_not_called()

    # Interesting characteristics of this test case:
    #  * CCLI number in the description of each song
    def test_summarize_20240505(self) -> None:
        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240505_summary.json")
        )
        actual_summary = get_plan_summary(
            client=self._pco_client,
            messenger=self._messenger,
            config=self._config,
            dt=date(2024, 5, 5),
        )

        self.assert_equal_summary(expected_summary, actual_summary)
        self._log_problem_mock.assert_not_called()

    def test_summarize_20250418_good_friday(self) -> None:
        plan = Plan(
            id=PlanId(service_type="1237521", plan="79927548"),
            date=date(year=2025, month=4, day=18),
            service_type_name="Good Friday & Communion - Watch & Pray",
            series_title="",
            title="",
            web_page_url="https://services.planningcenteronline.com/plans/79927548",
        )
        self._pco_client.find_plan_by_date = lambda _: plan  # pyright: ignore
        actual_summary = get_plan_summary(
            client=self._pco_client,
            messenger=self._messenger,
            config=self._config,
            dt=date(2025, 4, 18),
        )
        expected_summary = load_plan_summary(
            _DATA_DIR.joinpath("20250418_summary.json")
        )

        self.assert_equal_summary(expected=expected_summary, actual=actual_summary)
        self._log_problem_mock.assert_not_called()


class DiffPlanSummaryTestCase(PlanSummaryTestCase):
    def test_no_diff(self) -> None:
        original = load_plan_summary(_DATA_DIR.joinpath("20240414_summary.json"))
        edited = load_plan_summary(_DATA_DIR.joinpath("20240414_summary.json"))
        actual = diff_plan_summaries(old=original, new=edited)
        expected = PlanSummaryDiff(
            plan=Plan(
                id=PlanId(service_type="882857", plan="71699950"),
                service_type_name="10:30AM Sunday Gathering",
                series_title="WORTHY",
                title="Worthy Of The Feast",
                date=date(year=2024, month=4, day=14),
                web_page_url="https://services.planningcenteronline.com/plans/71699950",
            ),
            walk_in_slides=[
                NoOp("River’s Edge"),
                NoOp("Worthy Series Title Slide"),
                NoOp("Give Generously"),
                NoOp("The After Party"),
                NoOp("Website"),
                NoOp("Follow Us Instagram"),
            ],
            opener_video=[
                NoOp(AnnotatedItem(content="Welcome Opener Video", notes=[]))
            ],
            announcements=[
                NoOp("GIVING TALK"),
                NoOp("Prayer Ministry"),
                NoOp("After Party"),
                NoOp("See You Next Sunday"),
            ],
            songs=[
                [
                    NoOp(
                        AnnotatedSong(
                            Song(
                                ccli="7104200",
                                title="Echo",
                                author="Israel Houghton, Matthew Ntlele, Chris Brown, Steven Furtick, and Alexander Pappas",
                            ),
                            notes=[],
                            description="",
                        )
                    )
                ],
                [
                    NoOp(
                        AnnotatedSong(
                            Song(
                                ccli=None,
                                title="Different (Live at Mosaic, Los Angeles, 2023)",
                                author=None,
                            ),
                            notes=[],
                            description="",
                        )
                    ),
                    NoOp(
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
                        )
                    ),
                    NoOp(
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
                        )
                    ),
                ],
                [
                    NoOp(
                        AnnotatedSong(
                            Song(
                                ccli=None,
                                title="Song 5: DIFFERENT ",
                                author=None,
                            ),
                            notes=[],
                            description="",
                        )
                    ),
                ],
            ],
            bumper_video=[
                NoOp(AnnotatedItem(content="Worthy Sermon Bumper Video", notes=[]))
            ],
            message=[
                NoOp("Worthy Of The Feast"),
                NoOp("Matthew 22:1-14 NLT"),
                NoOp("Our Worth Isn’t Earned It’s Given"),
                NoOp("Matthew 22:4"),
                NoOp("Our Worth Is Experienced Through Acceptance"),
                NoOp("Matthew 22:10"),
                NoOp("Our Worth Is Revealed By Our Garments"),
                NoOp("Matthew 22:11"),
                NoOp("You Are Worthy Because You Are Chosen"),
                NoOp("Matthew 22:14"),
                NoOp("Our Worth Is Connected To Our Embrace Of The Worth Of The Feast"),
                NoOp("Our worth is experienced  through\tacceptance  "),
                NoOp("Live According To The Level Of Worth We Have Received"),
            ],
            message_warnings=[
                NoOp(
                    ItemNote(
                        category="Warning",
                        contents='There are duplicate lines in the sermon notes ("our worth is experienced through acceptance"). Check with Pastor Lorenzo that this is intentional.',
                    )
                )
            ],
            num_visuals_notes=2,
        )
        self.assert_equal_summary_diff(expected, actual)
        self.assertEqual(False, actual.plan_changed)
        self.assertEqual(False, actual.walk_in_slides_changed)
        self.assertEqual(False, actual.announcements_changed)
        self.assertEqual(False, actual.videos_changed)
        self.assertEqual(False, actual.songs_changed)
        self.assertEqual(False, actual.message_changed)

    def test_diff_20240414(self) -> None:
        original = load_plan_summary(_DATA_DIR.joinpath("20240414_summary.json"))
        edited = load_plan_summary(_DATA_DIR.joinpath("20240414_summary_edited.json"))
        actual = diff_plan_summaries(old=original, new=edited)
        expected = PlanSummaryDiff(
            plan=Plan(
                id=PlanId(service_type="882857", plan="71699950"),
                service_type_name="10:30AM Sunday Gathering",
                series_title="Worthy",
                title="Worthy of the feast",
                date=date(year=2024, month=4, day=14),
                web_page_url="https://services.planningcenteronline.com/plans/71699950",
            ),
            walk_in_slides=[
                NoOp("River’s Edge"),
                NoOp("Worthy Series Title Slide"),
                Deletion("Give Generously"),
                Deletion("The After Party"),
                Deletion("Website"),
                Deletion("Follow Us Instagram"),
                Insertion("Give with us"),
                Insertion("The after party"),
                Insertion("River's Edge website"),
            ],
            opener_video=[
                Deletion(AnnotatedItem(content="Welcome Opener Video", notes=[])),
                Insertion(AnnotatedItem(content="New Opener Video", notes=[])),
            ],
            announcements=[
                Deletion("GIVING TALK"),
                Insertion("Giving Talk"),
                NoOp("Prayer Ministry"),
                NoOp("After Party"),
                NoOp("See You Next Sunday"),
            ],
            songs=[
                [
                    NoOp(
                        AnnotatedSong(
                            Song(
                                ccli="7104200",
                                title="Echo",
                                author="Israel Houghton, Matthew Ntlele, Chris Brown, Steven Furtick, and Alexander Pappas",
                            ),
                            notes=[],
                            description="",
                        )
                    )
                ],
                [
                    Deletion(
                        AnnotatedSong(
                            Song(
                                ccli=None,
                                title="Different (Live at Mosaic, Los Angeles, 2023)",
                                author=None,
                            ),
                            notes=[],
                            description="",
                        )
                    ),
                    Insertion(
                        AnnotatedSong(
                            Song(
                                ccli="No CCLI number",
                                title="Different (Live at Mosaic, Los Angeles, 2023)",
                                author=None,
                            ),
                            notes=[],
                            description="",
                        )
                    ),
                    NoOp(
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
                        )
                    ),
                    Deletion(
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
                        )
                    ),
                ],
                [
                    Insertion(
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
                        )
                    ),
                    NoOp(
                        AnnotatedSong(
                            Song(
                                ccli=None,
                                title="Song 5: DIFFERENT ",
                                author=None,
                            ),
                            notes=[],
                            description="",
                        )
                    ),
                ],
            ],
            bumper_video=[
                Deletion(AnnotatedItem(content="Worthy Sermon Bumper Video", notes=[])),
                Insertion(AnnotatedItem(content="New Bumper Video", notes=[])),
            ],
            message=[
                NoOp("Worthy Of The Feast"),
                NoOp("Matthew 22:1-14 NLT"),
                NoOp("Our Worth Isn’t Earned It’s Given"),
                NoOp("Matthew 22:4"),
                NoOp("Our Worth Is Experienced Through Acceptance"),
                NoOp("Matthew 22:10"),
                NoOp("Our Worth Is Revealed By Our Garments"),
                NoOp("Matthew 22:11"),
                NoOp("You Are Worthy Because You Are Chosen"),
                NoOp("Matthew 22:14"),
                NoOp("Our Worth Is Connected To Our Embrace Of The Worth Of The Feast"),
                Deletion("Our worth is experienced  through\tacceptance  "),
                NoOp("Live According To The Level Of Worth We Have Received"),
                Insertion("New line"),
                Insertion("Another new line"),
            ],
            message_warnings=[
                Deletion(
                    ItemNote(
                        category="Warning",
                        contents='There are duplicate lines in the sermon notes ("our worth is experienced through acceptance"). Check with Pastor Lorenzo that this is intentional.',
                    )
                )
            ],
            num_visuals_notes=2,
        )
        self.assert_equal_summary_diff(expected, actual)
        self.assertEqual(True, actual.plan_changed)
        self.assertEqual(True, actual.walk_in_slides_changed)
        self.assertEqual(True, actual.announcements_changed)
        self.assertEqual(True, actual.videos_changed)
        self.assertEqual(True, actual.songs_changed)
        self.assertEqual(True, actual.message_changed)


class PlanSummaryToHtmlTestCase(unittest.TestCase):
    """Test `plan_summary_to_html()`."""

    def setUp(self) -> None:
        self.maxDiff = None

    def test_copy_message_notes(self) -> None:
        """
        Test that the message notes can be copied from the HTML summary.
        """
        original_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240414_summary.json")
        )
        edited_summary = load_plan_summary(
            _DATA_DIR.joinpath("20240414_summary_edited.json")
        )
        diff = diff_plan_summaries(original_summary, edited_summary)
        summary_html = plan_summary_diff_to_html(
            diff, old_plans=[], current_plan_id="", port=8080
        )
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
            Live According To The Level Of Worth We Have Received
            New line
            Another new line"""
        )
        self.assertEqual(expected_text, _get_clipboard_text())


class PlanSummaryJsonTestCase(PlanSummaryTestCase):
    SUMMARY = PlanSummary(
        plan=Plan(
            id=PlanId(service_type="882857", plan="71699950"),
            service_type_name="10:30AM Sunday Gathering",
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
        songs=[
            [
                AnnotatedSong(
                    Song(
                        ccli="7104200",
                        title="Echo",
                        author="Israel Houghton, Matthew Ntlele, Chris Brown, Steven Furtick, and Alexander Pappas",
                    ),
                    notes=[],
                    description="",
                )
            ],
            [
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
            ],
            [  # No linked song at all
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
                n += 1
                summary1 = load_plan_summary(p)
                temp_file = _TEMP_DIR.joinpath(p.relative_to(_DATA_DIR))
                temp_file.write_text(plan_summary_to_json(summary1))
                summary2 = load_plan_summary(temp_file)
                self.assert_equal_summary(summary1, summary2)
        # At least one test must have run, otherwise there's something wrong
        # with the test itself
        self.assertGreater(n, 0)


class GetVocalsNotesTestCase(PlanSummaryTestCase):
    """Test `get_vocals_notes()`."""

    def setUp(self):
        super().setUp()
        (
            self._config,
            self._messenger,
            self._log_problem_mock,
            self._pco_client,
        ) = self.create_services()

    def test_get_vocals_notes_20240505(self) -> None:
        expected_notes = [
            AnnotatedSong(
                song=Song(
                    ccli=None,
                    title="Come Now Is The Time To Worship (C to A)",
                    author=None,
                ),
                notes=[
                    ItemNote(
                        category="Vocals",
                        contents="Lead: Rodger\nMelody: Iris (boost during last half of the song after we modulate in key of A)\nHarmony: Kristina",
                    )
                ],
                description="CCLI Song # 2430948",
            ),
            AnnotatedSong(
                song=Song(
                    ccli=None,
                    title="Miracle / All Hail King Jesus (C)",
                    author=None,
                ),
                notes=[
                    ItemNote(
                        category="Vocals",
                        contents="Lead: Kristina\nInstrumental V1 chords during MC Hosts speaking\nIntro\nV1 - Kristina\nChorus - Kristina\nTurnaround\nV2 - All (uni)\nChorus - All (harms)\nBridge\n(2X) All Hail King Jesus Chorus 1A (harms)\n(1X) All Hail King Jesus Chorus 1B\nTurnaround\nV3 - Kristina (first 2 lines) / (last 2 lines all in - harms)\n(2X) All Hail King Jesus Chorus 1A (harms)\n(1X) All Hail King Jesus Chorus 1B",
                    )
                ],
                description="Miracle: CCLI Song # 7118762\nAll Hail King Jesus: CCLI Song # 7097216",
            ),
            AnnotatedSong(
                song=Song(
                    ccli=None,
                    title="How Deep The Father's Love For Us / He Lives (B)",
                    author=None,
                ),
                notes=[
                    ItemNote(
                        category="Vocals",
                        contents="Lead: Iris / Harmony: Kristina\nInstrumental V1 of What a Beautiful Name during communion\nV1 - Iris & Rodger\nTurnaround\nV2 - All (harms)\nTurnaround\nV3 - All (harms)\n(2X) He Lives - Chorus - All (harms)\nHe Lives (Instrumental)\n(2X) He Lives Bridge  - All (harms)\n(2X) He Lives - Chorus - All (harms)\nHe Lives (Instrumental)\nV1 - Iris & Rodger\nStay on B to transition to What a Beautiful Name",
                    )
                ],
                description="How Deep The Father's Love For Us: CCLI Song # 1558110\nHe Lives: CCLI Song # 7133098",
            ),
            AnnotatedSong(
                song=Song(
                    ccli=None,
                    title="What a Beautiful Name / Agnus Dei (B)",
                    author=None,
                ),
                notes=[
                    ItemNote(
                        category="Vocals",
                        contents="Lead: Kristina\nV1 - Kristina\nChorus 1 - Kristina\nV2 - All (harms)\nChorus 2 - All (harms)\nInstrumental\nBridge 1 - Kristina\nBridge 2 - All (harms)\nChorus 3 - All (harms)\nBridge 2 - All (harms) \n(2X) Agnus Dei Chorus - All (harms)\nChorus 1 - Kristina\nlast line tag 2X - Kristina",
                    )
                ],
                description="What a Beautiful Name: CCLI Song # 7068424\nAgnus Dei: CCLI Song # 626713",
            ),
            AnnotatedSong(
                song=Song(
                    ccli=None,
                    title="Worthy Of It All / I Exalt Thee (B)",
                    author=None,
                ),
                notes=[
                    ItemNote(
                        category="Vocals",
                        contents="Instrumental V1 of What a Beautiful Name during communion\nV1 - Iris & Rodger\nTurnaround\nV2 - All (harms)\nTurnaround\nV3 - All (harms)\n(2X) He Lives - Chorus - All (harms)\nHe Lives (Instrumental)\nV1 - Iris & Rodger\n(2X) He Lives - Chorus - All (harms)\nStay on B to transition to What a Beautiful Name",
                    )
                ],
                description="Worthy Of It All: CCLI Song #6280644\nI Exalt Thee: CCLI Song #17803",
            ),
        ]
        actual_notes = get_vocals_notes(
            client=self._pco_client,
            config=self._config,
            dt=date(2024, 5, 5),
        )

        self.assertEqual(actual_notes, expected_notes)
        self._log_problem_mock.assert_not_called()


def _get_clipboard_text() -> str:
    root = Tk()
    x = root.clipboard_get()
    root.quit()
    return x
