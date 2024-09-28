import unittest
from datetime import date
from typing import Tuple
from unittest.mock import create_autospec

from args import ReccArgs
from autochecklist import Messenger
from config import McrSetupConfig
from external_services import CredentialStore, InputPolicy, PlanningCenterClient
from lib import mcr_setup


class DownloadMessageNotesTestCase(unittest.TestCase):
    def test_download_valid_notes_20240915(self) -> None:
        config, client = _create_services(date(year=2024, month=9, day=15))
        expected_notes = """SIGNS God Is Speaking
God Is Trying To Get Your Attention
Are You Missing The Ways He’s Speaking To You?
God Is Always Listening
Psalm 66:17-20 NLT
How Do I Listen To God?
1 John 5:14-15 NLT
God Is Not Silent. He’s Just Speaking Differently Than You’re Expecting
1. God Speaks Through His Scriptures By Repeating
Job 33:14 NLT
2. God Speaks Audibly
Acts 9:4-7 NLT
3. God Uses Other People & Their Wise Counsel Verified Against His Word
1 John 4:1 NLT
4. God Is Speaking To You Through Visions & Dreams? God Is Warning - Encouraging - Instructing You
Acts 18:9 NLT
5. God Speaks Through An Inner Knowing
1 Kings 19:11-13 NLT
6. God Speaks By Blocking Your Path
Acts 16:6-8 NLT
Questions To Guide You
Is it agreeing with or contradicting the Scriptures?
Is it me tempting or testing God for proof?
Is it leading me to become more like Jesus?
Is this going to bless others or just me?
Is there an undeniable confidence in spite of a lack of human peace?
John 14:27 NLT
"""
        mcr_setup.download_message_notes(client, config)
        actual_notes = config.message_notes_file.read_text()
        self.assertEqual(actual_notes, expected_notes)

    def test_download_empty_notes_20240505(self) -> None:
        config, client = _create_services(date(year=2024, month=5, day=5))
        with self.assertRaises(ValueError) as cm:
            mcr_setup.download_message_notes(client, config)
        self.assertEqual(
            str(cm.exception), "No message notes have been posted to the plan yet."
        )


def _create_services(dt: date) -> Tuple[McrSetupConfig, PlanningCenterClient]:
    args = ReccArgs.parse(["", "--date", dt.strftime("%Y-%m-%d")])
    config = McrSetupConfig(
        args=args,
        profile="mcr_dev",
        strict=True,
        allow_multiple_only_for_testing=True,
    )
    messenger = create_autospec(Messenger)
    credential_store = CredentialStore(
        messenger=messenger, request_input=InputPolicy.NEVER
    )
    client = PlanningCenterClient(
        messenger=messenger,
        credential_store=credential_store,
        config=config,
    )
    return (config, client)
