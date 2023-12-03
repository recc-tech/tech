import unittest
from datetime import date
from typing import Any
from unittest.mock import Mock

import common.planning_center as pc
from autochecklist import Messenger
from common.credentials import CredentialStore


class PlanningCenterTestCase(unittest.TestCase):
    def test_find_plan_by_date(self):
        for lazy_login in {True, False}:
            with self.subTest(f"lazy_login={lazy_login}"):
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
                    lazy_login=lazy_login,
                )

                plan = client.find_plan_by_date(date(year=2023, month=11, day=26))
                self.assertEqual("66578821", plan.id)
                self.assertEqual("Rejected", plan.series_title)
                self.assertEqual("Rejected By God", plan.title)

                log_problem_mock.assert_not_called()
