from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Mapping, Optional

import dateutil.parser
import dateutil.tz
import requests
import webvtt
from autochecklist import Messenger, ProblemLevel
from config import Config
from requests.auth import HTTPBasicAuth

from .credentials import Credential, CredentialStore, InputPolicy


@dataclass
class Broadcast:
    id: str
    start_time: datetime


@dataclass
class Cue:
    start_time: float
    end_time: float
    text: str


class BoxCastApiClient:
    MAX_ATTEMPTS = 3

    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        config: Config,
        lazy_login: bool,
    ) -> None:
        self._messenger = messenger
        self._credential_store = credential_store
        self._config = config
        self._token: Optional[str] = None
        self._mutex = Lock()
        if not lazy_login:
            self._get_current_oauth_token(old_token=None)

    def find_main_broadcast_by_date(self, dt: date) -> Optional[Broadcast]:
        url = f"{self._config.boxcast_base_url}/account/broadcasts"
        params = {
            "l": "1",
            "s": "-starts_at",
            "filter.has_recording": "true",
            "q": f"starts_at:[{dt.strftime('%Y-%m-%dT00:00:00')} TO {dt.strftime('%Y-%m-%dT23:59:59')}]",
        }
        data = self._send_and_check("GET", url, params=params)
        if len(data) == 0:
            return None
        else:
            broadcast_json = data[0]
            return Broadcast(
                id=broadcast_json["id"],
                start_time=dateutil.parser.isoparse(broadcast_json["starts_at"]),
            )

    def download_captions(self, broadcast_id: str, path: Path) -> None:
        url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}/captions"
        json_captions = self._send_and_check("GET", url)
        if len(json_captions) == 0:
            raise ValueError("No captions found.")
        else:
            json_cues = json_captions[0]["cues"]
            cues = [
                Cue(
                    start_time=c["start_time"],
                    end_time=c["end_time"],
                    text=c["text"],
                )
                for c in json_cues
            ]
            _save_captions(cues, path)

    def _get_captions_id(self, broadcast_id: str) -> str:
        url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}/captions"
        json_captions = self._send_and_check("GET", url)
        if len(json_captions) == 0:
            raise ValueError("No captions found.")
        else:
            return json_captions[0]["id"]

    def upload_captions(self, broadcast_id: str, path: Path) -> None:
        captions_id = self._get_captions_id(broadcast_id=broadcast_id)
        url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}/captions/{captions_id}"
        cues = [
            {
                "start_time": c.start_time,
                "end_time": c.end_time,
                "text": c.text,
                # BoxCast seems to default to 1 when uploading via UI
                "confidence": 1,
            }
            for c in _load_captions(p=path)
        ]
        payload = {"cues": cues}
        self._send_and_check("PUT", url, json=payload)

    def schedule_rebroadcast(
        self, broadcast_id: str, name: str, start: datetime
    ) -> None:
        current_dt = datetime.combine(
            date=self._config.start_time.date(),
            time=datetime.now().time(),
        )
        if start <= current_dt:
            raise ValueError("Rebroadcast start time is in the past.")
        url = f"{self._config.boxcast_base_url}/account/broadcasts"
        start_utc = start.astimezone(dateutil.tz.tzutc())
        starts_at = start_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        payload = {
            "name": name,
            "stream_source": "recording",
            "source_broadcast_id": broadcast_id,
            "starts_at": starts_at,
            "is_private": False,
            "is_ticketed": False,
            "do_not_record": True,
            "requests_captioning": False,
        }
        headers = {"Content-Type": "application/json"}
        self._send_and_check(method="POST", url=url, json=payload, headers=headers)

    def export_to_vimeo(
        self, broadcast_id: str, vimeo_user_id: str, title: str
    ) -> None:
        recording_id = self._get_recording_id(broadcast_id=broadcast_id)
        url = f"{self._config.boxcast_base_url}/account/recordings/{recording_id}/vimeo_export"
        payload = {
            "vimeo_user_id": vimeo_user_id,
            "video_info": {"name": title, "description": ""},
        }
        self._send_and_check(method="POST", url=url, json=payload)

    def _get_recording_id(self, broadcast_id: str) -> str:
        url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}"
        data = self._send_and_check(method="GET", url=url)
        return data["recording_id"]

    def _send_and_check(
        self,
        method: str,
        url: str,
        params: Optional[Mapping[str, str]] = None,
        json: Optional[Mapping[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        headers = headers or {}
        self._messenger.log_debug(
            f"Attempting to send HTTP request {method} {url} with"
            + f" params {params}, data {json}, and headers {headers}"
        )
        token = None
        for i in range(self.MAX_ATTEMPTS):
            token = self._get_current_oauth_token(old_token=token)
            headers["Authorization"] = f"Bearer {token}"
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers,
                timeout=self._config.timeout_seconds,
            )
            if response.status_code // 100 == 2:
                return response.json()
            elif response.status_code == 401:
                self._messenger.log_problem(
                    ProblemLevel.WARN,
                    f"Request to {url} failed with status 401 (unauthorized)."
                    + f" Attempt {i + 1}/{self.MAX_ATTEMPTS}.",
                )
            else:
                msg = (
                    f"Request to {url} failed with status code {response.status_code}."
                )
                self._messenger.log_debug(f"{msg} Response body: {response.json()}\n")
                raise ValueError(msg)
        raise ValueError(f"Request to {url} failed ({self.MAX_ATTEMPTS} attempts).")

    def _get_current_oauth_token(self, old_token: Optional[str]) -> str:
        with self._mutex:
            if old_token is None and self._token is not None:
                # Caller doesn't have any token at all
                return self._token
            is_old_token_outdated = old_token != self._token
            if is_old_token_outdated and self._token is not None:
                # Try again with the latest token
                return self._token

            # The current token is apparently invalid! Request a fresh one
            for i in range(self.MAX_ATTEMPTS):
                try:
                    credentials = self._credential_store.get_multiple(
                        prompt="Enter the BoxCast API credentials.",
                        credentials=[
                            Credential.BOXCAST_CLIENT_ID,
                            Credential.BOXCAST_CLIENT_SECRET,
                        ],
                        # Maybe the first attempt failed because the stored
                        # credentials are wrong
                        request_input=(
                            InputPolicy.AS_REQUIRED if i == 0 else InputPolicy.ALWAYS
                        ),
                    )
                    client_id = credentials[Credential.BOXCAST_CLIENT_ID]
                    client_secret = credentials[Credential.BOXCAST_CLIENT_SECRET]
                    tok = self._get_new_oauth_token(
                        client_id=client_id, client_secret=client_secret
                    )
                    self._token = tok
                    return tok
                except ValueError:
                    self._messenger.log_problem(
                        ProblemLevel.WARN,
                        f"Failed to get OAuth token from the BoxCast API (attempt {i + 1}/{self.MAX_ATTEMPTS}).",
                        stacktrace=traceback.format_exc(),
                    )

            raise ValueError(
                f"Failed to get OAuth token from the BoxCast API ({self.MAX_ATTEMPTS} attempts)."
            )

    def _get_new_oauth_token(self, client_id: str, client_secret: str) -> str:
        auth = HTTPBasicAuth(client_id, client_secret)
        base_url = self._config.boxcast_auth_base_url
        response = requests.post(
            f"{base_url}/oauth2/token",
            data="grant_type=client_credentials",
            auth=auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._config.timeout_seconds,
        )
        if response.status_code // 100 != 2:
            raise ValueError(
                f"Token request failed with status code {response.status_code}."
            )
        data = response.json()
        return data["access_token"]


def _save_captions(cues: List[Cue], p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for i, c in enumerate(cues, start=1):
            start_td = timedelta(seconds=c.start_time)
            end_td = timedelta(seconds=c.end_time)
            f.write(f"{i}\n")
            f.write(f"{_format_timedelta(start_td)} --> {_format_timedelta(end_td)}\n")
            f.write(f"{c.text}\n\n")


def _load_captions(p: Path) -> List[Cue]:
    vtt = webvtt.read(p)
    vtt.captions
    return [
        Cue(start_time=c.start_in_seconds, end_time=c.end_in_seconds, text=c.text)
        for c in vtt.captions
    ]


def _format_timedelta(td: timedelta) -> str:
    tot_seconds = int(td.total_seconds())
    seconds = tot_seconds % 60
    minutes = (tot_seconds // 60) % 60
    hours = tot_seconds // (60 * 60)
    millis = td.microseconds // 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
