import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import mcr_teardown.tasks as tasks
from autochecklist.messenger import Messenger
from common import Credential, CredentialStore, InputPolicy
from mcr_teardown.boxcast import BoxCastClient, BoxCastClientFactory
from mcr_teardown.config import McrTeardownConfig

EVENT_ID = "oajqcyzetaazjvduyqz5"
BOXCAST_TEST_USERNAME = "tech@riversedge.life"


class BoxCastTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.error_message = ""
        messenger = Mock(spec=Messenger)
        credential_store = CredentialStore(messenger)
        boxcast_username = credential_store.get(
            Credential.BOXCAST_USERNAME, request_input=InputPolicy.AS_REQUIRED
        )
        if boxcast_username != BOXCAST_TEST_USERNAME:
            cls.error_message = f"Expected the BoxCast username to be '{BOXCAST_TEST_USERNAME}' but found username '{boxcast_username}'. Run python check_credentials.py --force-input to set the correct credentials."
            return
        try:
            BoxCastClientFactory(
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
            Path(__file__).parent.joinpath("test_home").joinpath(f"{timestamp}_home")
        )
        cls.home_dir.mkdir(exist_ok=True, parents=True)

    def setUp(self) -> None:
        if self.error_message:
            self.fail(self.error_message)

    def test_captions(self):
        messenger = Mock(spec=Messenger)
        log_problem_mock = Mock()
        messenger.log_problem = log_problem_mock
        credential_store = CredentialStore(messenger)
        boxcast_client = BoxCastClient(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
        )
        boxcast_client_factory = Mock(spec=["get_client"])
        boxcast_client_factory.get_client.return_value = boxcast_client  # type: ignore
        config = McrTeardownConfig(
            home_dir=self.home_dir,
            downloads_dir=Path(os.environ["USERPROFILE"]).joinpath("Downloads"),
            boxcast_event_id=EVENT_ID,
        )

        tasks.download_captions(
            boxcast_client_factory=boxcast_client_factory,
            config=config,
            messenger=messenger,
        )
        expected_file = Path(__file__).parent.joinpath("captions.vtt")
        with open(expected_file, mode="r", encoding="utf-8") as f:
            expected_captions = f.read()
        with open(config.original_captions_path, mode="r", encoding="utf-8") as f:
            actual_captions = f.read()
        self.assertEqual(expected_captions, actual_captions)
        log_problem_mock.assert_not_called()

        tasks.copy_captions_to_final(config=config)
        with open(config.original_captions_path, mode="r", encoding="utf-8") as f:
            captions_without_worship = f.read()
        with open(config.final_captions_path, mode="r", encoding="utf-8") as f:
            final_captions = f.read()
        self.assertEqual(captions_without_worship, final_captions)
        log_problem_mock.assert_not_called()
