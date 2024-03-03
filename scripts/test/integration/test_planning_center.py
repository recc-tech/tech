import asyncio
import filecmp
import inspect
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from typing import Tuple
from unittest.mock import Mock

from args import ReccArgs
from autochecklist import Messenger
from config import Config
from external_services import Attachment, CredentialStore, PlanningCenterClient

DATA_DIR = Path(__file__).parent.joinpath("planning_center_data")
TEMP_DIR = Path(__file__).parent.joinpath("planning_center_temp")


class PlanningCenterTestCase(unittest.TestCase):
    def test_find_plan_by_date(self) -> None:
        client, _, log_problem_mock = self._create_client()

        plan = client.find_plan_by_date(date(year=2023, month=11, day=26))

        self.assertEqual("66578821", plan.id)
        self.assertEqual("Rejected", plan.series_title)
        self.assertEqual("Rejected By God", plan.title)
        log_problem_mock.assert_not_called()

    def test_find_message_notes(self) -> None:
        client, _, log_problem_mock = self._create_client()
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

        actual_notes = client.find_message_notes("66578821")

        self.assertEqual(expected_message_notes, actual_notes)
        log_problem_mock.assert_not_called()

    def test_find_attachments(self) -> None:
        client, _, log_problem_mock = self._create_client()
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

        actual_attachments = client.find_attachments("64650350")

        self.assertEqual(expected_attachments, actual_attachments)
        log_problem_mock.assert_not_called()

    def test_download_assets(self) -> None:
        client, messenger, log_problem_mock = self._create_client()
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
            client.download_attachments(
                attachments, messenger=messenger, cancellation_token=None
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
        log_problem_mock.assert_not_called()

    def _create_client(self) -> Tuple[PlanningCenterClient, Messenger, Mock]:
        args = ReccArgs(
            Namespace(), lambda msg: self.fail(f"Argument parsing error: {msg}")
        )
        messenger = Mock(spec=Messenger)
        log_problem_mock = Mock()
        messenger.log_problem = log_problem_mock

        def input_mock(*args: object, **kwargs: object):
            raise ValueError(
                "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
            )

        messenger.input_multiple = input_mock
        messenger.input = input_mock
        messenger.wait = input_mock
        credential_store = CredentialStore(messenger)
        client = PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            config=Config(args),
            # Use a different value from test_find_message_notes
            lazy_login=False,
        )
        return client, messenger, log_problem_mock
