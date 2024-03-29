import unittest
from argparse import Namespace
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock

import lib.mcr_teardown as tasks
from autochecklist import Messenger
from config import McrTeardownArgs, McrTeardownConfig
from external_services import (
    BoxCastClientFactory,
    Credential,
    CredentialStore,
    InputPolicy,
)

EVENT_ID = "oajqcyzetaazjvduyqz5"
BOXCAST_TEST_USERNAME = "tech@riversedge.life"


class BoxCastTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def input_mock(*args: object, **kwargs: object):
            raise ValueError(
                "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
            )

        cls.error_message = ""
        cls.messenger = Mock(spec=Messenger)
        cls.log_problem_mock = Mock()
        cls.messenger.log_problem = cls.log_problem_mock
        cls.messenger.input_multiple = input_mock
        cls.messenger.input = input_mock
        cls.messenger.wait = input_mock
        credential_store = CredentialStore(cls.messenger)
        boxcast_username = credential_store.get(
            Credential.BOXCAST_USERNAME, request_input=InputPolicy.AS_REQUIRED
        )
        if boxcast_username != BOXCAST_TEST_USERNAME:
            cls.error_message = f"Expected the BoxCast username to be '{BOXCAST_TEST_USERNAME}' but found username '{boxcast_username}'. Run python check_credentials.py --force-input to set the correct credentials."
            return
        try:
            cls.boxcast_client_factory = BoxCastClientFactory(
                messenger=Mock(),
                credential_store=credential_store,
                cancellation_token=None,
                headless=True,
                lazy_login=False,
                log_directory=None,
                log_file_name=None,
            )
        except Exception as e:
            raise RuntimeError(
                "Failed to log in to BoxCast. Run python check_credentials.py to set the correct credentials."
            ) from e

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        cls.home_dir = (
            Path(__file__)
            .parent.joinpath("boxcast_test_home")
            .joinpath(f"{timestamp}_home")
        )
        cls.home_dir.mkdir(exist_ok=True, parents=True)

    def setUp(self) -> None:
        if self.error_message:
            self.fail(self.error_message)

    def test_captions(self):
        args = McrTeardownArgs(
            Namespace(
                message_series="",
                message_title="",
                boxcast_event_id=EVENT_ID,
                home_dir=self.home_dir,
                downloads_dir=Path.home().joinpath("Downloads"),
                lazy_login=True,
                date=date.today(),
                show_browser=False,
                ui="console",
                verbose=False,
                no_run=False,
                auto=None,
            ),
            lambda msg: self.fail(f"Argument parsing error: {msg}"),
        )
        config = McrTeardownConfig(args, allow_multiple_only_for_testing=True)

        tasks.download_captions(
            boxcast_client_factory=self.boxcast_client_factory,
            config=config,
            messenger=self.messenger,
        )
        expected_file = Path(__file__).parent.joinpath("boxcast_data", "captions.vtt")
        with open(expected_file, mode="r", encoding="utf-8") as f:
            expected_captions = f.read()
        with open(config.original_captions_file, mode="r", encoding="utf-8") as f:
            actual_captions = f.read()
        self.assertEqual(expected_captions, actual_captions)
        self.log_problem_mock.assert_not_called()

        tasks.copy_captions_to_final(config=config)
        with open(config.original_captions_file, mode="r", encoding="utf-8") as f:
            captions_without_worship = f.read()
        with open(config.final_captions_file, mode="r", encoding="utf-8") as f:
            final_captions = f.read()
        self.assertEqual(captions_without_worship, final_captions)
        self.log_problem_mock.assert_not_called()
