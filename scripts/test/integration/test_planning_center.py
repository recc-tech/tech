import asyncio
import filecmp
import inspect
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from args import ReccArgs
from autochecklist import Messenger
from config import Config
from external_services import (
    Attachment,
    CredentialStore,
    Plan,
    PlanId,
    PlanningCenterClient,
    PresenterSet,
    TeamMember,
    TeamMemberStatus,
)

DATA_DIR = Path(__file__).parent.joinpath("planning_center_data")
TEMP_DIR = Path(__file__).parent.joinpath("planning_center_temp")


class PlanningCenterTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()

        args = ReccArgs(
            Namespace(
                ui="tk",
                verbose=False,
                no_run=False,
                auto=None,
                date=None,
                auto_close=True,
            ),
            lambda msg: self.fail(f"Argument parsing error: {msg}"),
        )
        self._messenger = Mock(spec=Messenger)
        self._log_problem_mock = Mock()
        self._messenger.log_problem = self._log_problem_mock

        def input_mock(*args: object, **kwargs: object):
            raise ValueError(
                "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
            )

        self._messenger.input_multiple = input_mock
        self._messenger.input = input_mock
        self._messenger.wait = input_mock
        credential_store = CredentialStore(self._messenger)
        config = Config(args, allow_multiple_only_for_testing=True)
        self._client = PlanningCenterClient(
            messenger=self._messenger,
            credential_store=credential_store,
            config=config,
            # Use a different value from test_find_message_notes
            lazy_login=False,
        )

    def test_find_plan_by_date_sunday(self) -> None:
        plan = self._client.find_plan_by_date(date(year=2023, month=11, day=26))

        self.assertEqual(PlanId(service_type="882857", plan="66578821"), plan.id)
        self.assertEqual("Rejected", plan.series_title)
        self.assertEqual("Rejected By God", plan.title)
        self._log_problem_mock.assert_not_called()

    def test_find_plan_by_date_good_friday(self) -> None:
        plan = self._client.find_plan_by_date(date(year=2025, month=4, day=18))

        expected_plan = Plan(
            id=PlanId(service_type="1237521", plan="79927548"),
            date=date(year=2025, month=4, day=18),
            service_type_name="Good Friday & Communion - Watch & Pray",
            series_title="",
            title="",
            web_page_url="https://services.planningcenteronline.com/plans/79927548",
        )
        self.assertEqual(plan, expected_plan)
        self._log_problem_mock.assert_not_called()

    def test_find_message_notes(self) -> None:
        expected_message_notes = inspect.cleandoc(
            """New Series: Let There Be Joy - Slide
            Rejected By God
            John 5:1-17 NASB Change the word Pallet for Mat where it appears in this text.
            Jesus asked, Do You Want to Get Well?
            Jesus understands when our desire to be healed is gone.
            When You Believe You’re Rejected By God
            Your Reasons Become Your Only Reality
            God created us to get up and walk, not to lie down in disappointment and defeat.
            Jesus Gives An Impossible Command To Obey When
            We Need a breakthrough moment to believe the impossible.

            Jesus Then Tells Him To Pick Up The Mat
            What To Pick Up?
            Pick Up Your Mat! You Won’t Depend On This Ever Again
            Pick Up Your Mat! That’s Not Who You Are Anymore 
            Pick Up Your Mat! You Won’t Ever Be Coming Back
            Leave This Place of Rejection Behind
            Superstition & Religion tells you to lie down on your Mat And Rest.
            Jesus Tells You To Get Up, Pick Up Your Mat and Walk!
            Matthew 27:46 NASB
            Matthew 16:24-25 NASB
            That’s Why Picking Up Our Mat Is Picking Up Our Cross
            You Carry Your Story of Past Illness And Healing.
            All We Need Is Jesus – Everyday He’s All We Need."""
        )

        actual_notes = self._client.find_message_notes(
            PlanId(service_type="882857", plan="66578821")
        )

        self.assertEqual(expected_message_notes, actual_notes)
        self._log_problem_mock.assert_not_called()

    def test_find_attachments(self) -> None:
        # It would be nice to test on a plan with more attachments (images,
        # videos, etc.), but the attachments seem to disappear quite quickly
        # after a service
        expected_attachments = {
            Attachment(
                id="145052830",
                filename="MC Host Script.docx",
                num_bytes=26_743,
                pco_filetype="file",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            Attachment(
                id="145057054",
                filename="Notes - Easter Experience - The Unexpected Road Trip.docx",
                num_bytes=17_167,
                pco_filetype="file",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        }

        actual_attachments = self._client.find_attachments(
            PlanId(service_type="882857", plan="64650350")
        )

        self.assertEqual(expected_attachments, actual_attachments)
        self._log_problem_mock.assert_not_called()

    def test_download_assets(self) -> None:
        expected_notes_path = DATA_DIR.joinpath("2023-04-16 Notes.docx")
        actual_notes_path = TEMP_DIR.joinpath("2023-04-16 Notes.docx")
        expected_script_path = DATA_DIR.joinpath("2023-04-16 MC Host Script.docx")
        actual_script_path = TEMP_DIR.joinpath("2023-04-16 MC Host Script.docx")
        # Get rid of old files so tests don't pass if download failed!
        actual_notes_path.unlink(missing_ok=True)
        actual_script_path.unlink(missing_ok=True)
        # The client expects the directories to actually exist
        DATA_DIR.mkdir(exist_ok=True)
        TEMP_DIR.mkdir(exist_ok=True)
        attachments = {
            actual_script_path: Attachment(
                id="145052830",
                filename="MC Host Script.docx",
                num_bytes=26_743,
                pco_filetype="file",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            actual_notes_path: Attachment(
                id="145057054",
                filename="Notes - Easter Experience - The Unexpected Road Trip.docx",
                num_bytes=17_167,
                pco_filetype="file",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        }

        results = asyncio.run(
            self._client.download_attachments(
                attachments, messenger=self._messenger, cancellation_token=None
            )
        )

        self.assertEqual({actual_script_path: None, actual_notes_path: None}, results)
        self.assertTrue(
            filecmp.cmp(expected_notes_path, actual_notes_path, shallow=False),
            "Message notes files must match.",
        )
        self.assertTrue(
            filecmp.cmp(expected_script_path, actual_script_path, shallow=False),
            "MC host script files must match.",
        )
        self._log_problem_mock.assert_not_called()

    def test_find_presenters_20250302(self) -> None:
        expected_presenters = PresenterSet(
            speakers={
                TeamMember(
                    name="Lorenzo DellaForesta", status=TeamMemberStatus.CONFIRMED
                )
            },
            hosts={
                TeamMember(
                    name="Maria Garcia Carrasco", status=TeamMemberStatus.CONFIRMED
                ),
                TeamMember(name="Paul Hanash", status=TeamMemberStatus.UNCONFIRMED),
            },
        )
        actual_presenters = self._client.find_presenters(
            PlanId(service_type="882857", plan="78328967")
        )
        self.assertEqual(actual_presenters, expected_presenters)
        self._log_problem_mock.assert_not_called()
