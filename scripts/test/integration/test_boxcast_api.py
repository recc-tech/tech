import unittest
from datetime import date, datetime
from unittest.mock import create_autospec

from args import ReccArgs
from autochecklist import Messenger
from config import Config
from dateutil.tz import tzutc
from external_services import BoxCastApiClient, Broadcast, CredentialStore, InputPolicy


class BoxCastTestCase(unittest.TestCase):
    def test_get_main_broadcast_20240505(self) -> None:
        messenger = create_autospec(Messenger)
        messenger.input_multiple = self._input_mock
        messenger.input = self._input_mock
        messenger.wait = self._input_mock
        credential_store = CredentialStore(
            messenger=messenger, request_input=InputPolicy.NEVER
        )
        config = Config(ReccArgs.parse([]), allow_multiple_only_for_testing=True)
        client = BoxCastApiClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            # TODO: Test both cases?
            lazy_login=False,
        )
        broadcast = client.find_main_broadcast_by_date(date(year=2024, month=5, day=5))
        self.assertEqual(
            Broadcast(
                id="orn5qh81x7dojxwlbbng",
                start_time=datetime(
                    # UTC
                    year=2024,
                    month=5,
                    day=5,
                    hour=14,
                    minute=25,
                    second=0,
                    tzinfo=tzutc(),
                ),
            ),
            broadcast,
        )

    def test_get_main_broadcast_20240506(self) -> None:
        messenger = create_autospec(Messenger)
        messenger.input_multiple = self._input_mock
        messenger.input = self._input_mock
        messenger.wait = self._input_mock
        credential_store = CredentialStore(
            messenger=messenger, request_input=InputPolicy.NEVER
        )
        config = Config(ReccArgs.parse([]), allow_multiple_only_for_testing=True)
        client = BoxCastApiClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            # TODO: Test both cases?
            lazy_login=False,
        )
        broadcast = client.find_main_broadcast_by_date(date(year=2024, month=5, day=6))
        self.assertEqual(None, broadcast)

    def _input_mock(*args: object, **kwargs: object):
        raise ValueError(
            "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
        )
