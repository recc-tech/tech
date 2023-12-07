import inspect
import unittest
from datetime import date
from typing import Any
from unittest.mock import Mock

import common.planning_center as pc
from autochecklist import Messenger
from common.credentials import CredentialStore


class PlanningCenterTestCase(unittest.TestCase):
    def test_find_plan_by_date(self):
        messenger = Mock(spec=Messenger)
        log_problem_mock = Mock()
        messenger.log_problem = log_problem_mock

        def input_mock(*args: Any, **kwargs: Any):
            raise ValueError(
                "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
            )

        messenger.input_multiple = input_mock
        messenger.input = input_mock
        messenger.wait = input_mock
        credential_store = CredentialStore(messenger)
        client = pc.PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            # Use a different value from test_find_message_notes
            lazy_login=False,
        )

        plan = client.find_plan_by_date(date(year=2023, month=11, day=26))
        self.assertEqual("66578821", plan.id)
        self.assertEqual("Rejected", plan.series_title)
        self.assertEqual("Rejected By God", plan.title)

        log_problem_mock.assert_not_called()

    def test_find_message_notes(self):
        messenger = Mock(spec=Messenger)
        log_problem_mock = Mock()
        messenger.log_problem = log_problem_mock

        def input_mock(*args: Any, **kwargs: Any):
            raise ValueError(
                "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
            )

        messenger.input_multiple = input_mock
        messenger.input = input_mock
        messenger.wait = input_mock
        credential_store = CredentialStore(messenger)
        client = pc.PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            # Use a different value from test_find_message_notes
            lazy_login=False,
        )

        actual_notes = client.find_message_notes("66578821")
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
        self.assertEqual(expected_message_notes, actual_notes)

        log_problem_mock.assert_not_called()
