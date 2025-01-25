import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import Mock, create_autospec

import captions
from args import ReccArgs
from autochecklist import Messenger
from captions import Cue
from config import Config
from dateutil.tz import tzutc
from external_services import (
    BoxCastApiClient,
    Broadcast,
    BroadcastInPastError,
    Credential,
    CredentialStore,
    InputPolicy,
)

_BROADCAST_20240505_ID = "orn5qh81x7dojxwlbbng"
_EXPECTED_CAPTIONS_20240505 = Path(__file__).parent.joinpath(
    "boxcast_api_data", "captions_20240505.vtt"
)
_ACTUAL_CAPTIONS_20240505 = Path(__file__).parent.joinpath(
    "boxcast_temp", "captions_20240505.vtt"
)


class BoxCastTestCase(unittest.TestCase):
    def test_get_main_broadcast_20240505(self) -> None:
        (client, log_problem_mock, _) = _set_up_dependencies()
        broadcast = client.find_main_broadcast_by_date(date(year=2024, month=5, day=5))
        expected_start_time = datetime(
            year=2024, month=5, day=5, hour=14, minute=25, second=0, tzinfo=tzutc()
        )
        self.assertEqual(
            Broadcast(id=_BROADCAST_20240505_ID, start_time=expected_start_time),
            broadcast,
        )
        log_problem_mock.assert_not_called()

    def test_get_main_broadcast_20240505_lazy(self) -> None:
        (client, log_problem_mock, _) = _set_up_dependencies(lazy_login=True)
        broadcast = client.find_main_broadcast_by_date(date(year=2024, month=5, day=5))
        expected_start_time = datetime(
            year=2024, month=5, day=5, hour=14, minute=25, second=0, tzinfo=tzutc()
        )
        self.assertEqual(
            Broadcast(id=_BROADCAST_20240505_ID, start_time=expected_start_time),
            broadcast,
        )
        log_problem_mock.assert_not_called()

    def test_get_main_broadcast_20240506(self) -> None:
        (client, log_problem_mock, _) = _set_up_dependencies()
        broadcast = client.find_main_broadcast_by_date(date(year=2024, month=5, day=6))
        self.assertEqual(None, broadcast)
        log_problem_mock.assert_not_called()

    def test_download_and_upload_captions_20240505(self) -> None:
        # Test downloading and immediately re-uploading to look for the bug in
        # https://github.com/recc-tech/tech/issues/337
        (client, log_problem_mock, _) = _set_up_dependencies()

        client.download_captions(
            broadcast_id=_BROADCAST_20240505_ID, path=_ACTUAL_CAPTIONS_20240505
        )
        expected_captions = list(captions.load(_EXPECTED_CAPTIONS_20240505))
        actual_captions = list(captions.load(_ACTUAL_CAPTIONS_20240505))
        self.assertEqual(expected_captions[1:], actual_captions[1:])
        expected_first_cue = expected_captions[0]
        actual_first_cue = actual_captions[0]
        self.assertEqual(expected_first_cue.id, actual_first_cue.id)
        self.assertEqual(expected_first_cue.start, actual_first_cue.start)
        self.assertEqual(expected_first_cue.end, actual_first_cue.end)
        self.assertEqual(expected_first_cue.confidence, actual_first_cue.confidence)
        log_problem_mock.assert_not_called()

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_first_cue = Cue(
            id=expected_first_cue.id,
            start=expected_first_cue.start,
            end=expected_first_cue.end,
            text=f"[Updated {now}]",
            confidence=expected_first_cue.confidence,
        )
        modified_captions = [new_first_cue] + expected_captions[1:]
        captions.save(modified_captions, _ACTUAL_CAPTIONS_20240505)
        client.upload_captions(
            broadcast_id=_BROADCAST_20240505_ID,
            path=_ACTUAL_CAPTIONS_20240505,
            cancellation_token=None,
        )
        log_problem_mock.assert_not_called()

        # Upload twice to test that uploading when other captions are possibly
        # still being published works (this may result in HTTP 409)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_first_cue = Cue(
            id=expected_first_cue.id,
            start=expected_first_cue.start,
            end=expected_first_cue.end,
            text=f"[Updated {now}]",
            confidence=expected_first_cue.confidence,
        )
        modified_captions = [new_first_cue] + expected_captions[1:]
        captions.save(modified_captions, _ACTUAL_CAPTIONS_20240505)
        client.upload_captions(
            broadcast_id=_BROADCAST_20240505_ID,
            path=_ACTUAL_CAPTIONS_20240505,
            cancellation_token=None,
        )
        log_problem_mock.assert_not_called()

        client.download_captions(
            broadcast_id=_BROADCAST_20240505_ID, path=_ACTUAL_CAPTIONS_20240505
        )
        redownloaded_captions = list(captions.load(_ACTUAL_CAPTIONS_20240505))
        self.assertEqual(modified_captions, redownloaded_captions)
        log_problem_mock.assert_not_called()

    # IMPORTANT: These tests MUST NOT actually create new rebroadcasts
    # Instead, test those things manually so that the tester can go and clean
    # up as needed

    def test_schedule_valid_rebroadcast(self) -> None:
        # Use a date in the past so that, if somehow the request goes through
        # to BoxCast, it will fail
        today = date(year=1999, month=12, day=25)
        (client, log_problem_mock, credential_store) = _set_up_dependencies(
            lazy_login=True, fake_credentials=True, today=today
        )
        # Make sure the credential store doesn't provide valid credentials so
        # that we don't actually send a request to BoxCast
        self._assert_credentials_are_fake(credential_store)
        send_mock = Mock()
        client._send_and_check = send_mock  # pyright: ignore[reportPrivateUsage]
        client._get_new_oauth_token = _fake_tok  # pyright: ignore[reportPrivateUsage]
        client.schedule_rebroadcast(
            broadcast_id="test_id",
            name="Test Broadcast",
            start=datetime.combine(
                date=today + timedelta(days=1),
                time=time(hour=1, minute=59, second=42),
            ),
        )
        send_mock.assert_called_once_with(
            method="POST",
            url="https://rest.boxcast.com/account/broadcasts",
            json={
                "name": "Test Broadcast",
                "stream_source": "recording",
                "source_broadcast_id": "test_id",
                "starts_at": "1999-12-26T06:59:42.000Z",
                "is_private": False,
                "is_ticketed": False,
                "do_not_record": True,
                "requests_captioning": False,
            },
            headers={"Content-Type": "application/json"},
        )
        log_problem_mock.assert_not_called()

    def test_schedule_valid_rebroadcast_daylight_savings(self) -> None:
        # Use a date in the past so that, if somehow the request goes through
        # to BoxCast, it will fail
        today = date(year=1999, month=6, day=3)
        (client, log_problem_mock, credential_store) = _set_up_dependencies(
            lazy_login=True, fake_credentials=True, today=today
        )
        # Make sure the credential store doesn't provide valid credentials so
        # that we don't actually send a request to BoxCast
        self._assert_credentials_are_fake(credential_store)
        send_mock = Mock()
        client._send_and_check = send_mock  # pyright: ignore[reportPrivateUsage]
        client._get_new_oauth_token = _fake_tok  # pyright: ignore[reportPrivateUsage]
        client.schedule_rebroadcast(
            broadcast_id="test_id",
            name="Test Broadcast",
            start=datetime.combine(
                date=today + timedelta(days=1),
                time=time(hour=1, minute=0, second=0),
            ),
        )
        send_mock.assert_called_once_with(
            method="POST",
            url="https://rest.boxcast.com/account/broadcasts",
            json={
                "name": "Test Broadcast",
                "stream_source": "recording",
                "source_broadcast_id": "test_id",
                "starts_at": "1999-06-04T05:00:00.000Z",
                "is_private": False,
                "is_ticketed": False,
                "do_not_record": True,
                "requests_captioning": False,
            },
            headers={"Content-Type": "application/json"},
        )
        log_problem_mock.assert_not_called()

    def test_schedule_rebroadcast_earlier_today(self) -> None:
        # Use a date in the past so that, if somehow the request goes through
        # to BoxCast, it will fail
        today = date(year=1999, month=1, day=2)
        (client, _, credential_store) = _set_up_dependencies(
            lazy_login=True, fake_credentials=True, today=today
        )
        # Make sure the credential store doesn't provide valid credentials so
        # that we don't actually send a request to BoxCast
        self._assert_credentials_are_fake(credential_store)
        send_mock = Mock()
        client._send_and_check = send_mock  # pyright: ignore[reportPrivateUsage]
        client._get_new_oauth_token = _fake_tok  # pyright: ignore[reportPrivateUsage]
        with self.assertRaises(BroadcastInPastError) as cm:
            client.schedule_rebroadcast(
                broadcast_id="test_id",
                name="Test Broadcast",
                start=(
                    datetime.combine(date=today, time=datetime.now().time())
                    - timedelta(minutes=1)
                ),
            )
        send_mock.assert_not_called()
        self.assertEqual("Rebroadcast start time is in the past.", str(cm.exception))

    def _assert_credentials_are_fake(self, credential_store: CredentialStore) -> None:
        self.assertEqual(
            {
                Credential.BOXCAST_CLIENT_ID: "FAKE CREDENTIAL",
                Credential.BOXCAST_CLIENT_SECRET: "FAKE CREDENTIAL",
            },
            credential_store.get_multiple(
                prompt="",
                credentials=[
                    Credential.BOXCAST_CLIENT_ID,
                    Credential.BOXCAST_CLIENT_SECRET,
                ],
                request_input=InputPolicy.NEVER,
            ),
        )


def _set_up_dependencies(
    lazy_login: bool = False,
    fake_credentials: bool = False,
    today: Optional[date] = None,
) -> Tuple[BoxCastApiClient, Mock, CredentialStore]:
    messenger = create_autospec(Messenger)
    messenger.input_multiple = _input_mock
    messenger.input = _input_mock
    messenger.wait = _input_mock
    log_problem_mock: Mock = messenger.log_problem
    if fake_credentials:
        credential_store = create_autospec(CredentialStore)
        credential_store.get_multiple = _get_fake_credentials
    else:
        credential_store = CredentialStore(
            messenger=messenger, request_input=InputPolicy.NEVER
        )
    args = [] if today is None else ["", "--date", today.strftime("%Y-%m-%d")]
    config = Config(
        ReccArgs.parse(args), allow_multiple_only_for_testing=True, create_dirs=True
    )
    client = BoxCastApiClient(
        messenger=messenger,
        credential_store=credential_store,
        config=config,
        lazy_login=lazy_login,
    )
    return (client, log_problem_mock, credential_store)


def _input_mock(*args: object, **kwargs: object):
    raise ValueError(
        "Taking input during testing is not possible. If you need credentials, enter them before running the tests using check_credentials.py."
    )


def _get_fake_credentials(
    prompt: str, credentials: List[Credential], request_input: InputPolicy
) -> Dict[Credential, str]:
    return {c: "FAKE CREDENTIAL" for c in credentials}


def _fake_tok(*args: object, **kwargs: object) -> str:
    return "FAKE TOKEN"
