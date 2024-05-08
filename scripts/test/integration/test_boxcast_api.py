import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, create_autospec

from args import ReccArgs
from autochecklist import Messenger
from config import Config
from dateutil.tz import tzutc
from external_services import BoxCastApiClient, Broadcast, CredentialStore, InputPolicy

BROADCAST_20240505_ID = "orn5qh81x7dojxwlbbng"
EXPECTED_CAPTIONS_20240505 = Path(__file__).parent.joinpath(
    "boxcast_api_data", "captions_20240505.vtt"
)
ACTUAL_CAPTIONS_20240505 = Path(__file__).parent.joinpath(
    "boxcast_temp", "captions_20240505.vtt"
)


class BoxCastTestCase(unittest.TestCase):
    def setUp(self) -> None:
        messenger = create_autospec(Messenger)
        messenger.input_multiple = self._input_mock
        messenger.input = self._input_mock
        messenger.wait = self._input_mock
        self.log_problem_mock: Mock = messenger.log_problem
        credential_store = CredentialStore(
            messenger=messenger, request_input=InputPolicy.NEVER
        )
        config = Config(ReccArgs.parse([]), allow_multiple_only_for_testing=True)
        self.client = BoxCastApiClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            # TODO: Test both cases?
            lazy_login=False,
        )

    def test_get_main_broadcast_20240505(self) -> None:
        broadcast = self.client.find_main_broadcast_by_date(
            date(year=2024, month=5, day=5)
        )
        expected_start_time = datetime(
            year=2024, month=5, day=5, hour=14, minute=25, second=0, tzinfo=tzutc()
        )
        self.assertEqual(
            Broadcast(id=BROADCAST_20240505_ID, start_time=expected_start_time),
            broadcast,
        )
        self.log_problem_mock.assert_not_called()

    def test_get_main_broadcast_20240506(self) -> None:
        broadcast = self.client.find_main_broadcast_by_date(
            date(year=2024, month=5, day=6)
        )
        self.assertEqual(None, broadcast)
        self.log_problem_mock.assert_not_called()

    def test_download_captions_20240505(self) -> None:
        self.client.download_captions(
            broadcast_id=BROADCAST_20240505_ID, path=ACTUAL_CAPTIONS_20240505
        )
        self.assertEqual(
            EXPECTED_CAPTIONS_20240505.read_text(), ACTUAL_CAPTIONS_20240505.read_text()
        )
        self.log_problem_mock.assert_not_called()

    def _input_mock(*args: object, **kwargs: object):
        raise ValueError(
            "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
        )
