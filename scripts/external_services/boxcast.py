from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse

import autochecklist
import captions
import dateutil.parser
import requests
from autochecklist import CancellationToken, Messenger, ProblemLevel
from captions import Cue
from config import Config
from requests import Response
from requests.auth import HTTPBasicAuth

from .credentials import Credential, CredentialStore, InputPolicy


@dataclass
class Broadcast:
    id: str
    start_time: datetime


class NoCaptionsError(Exception):
    pass


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

    def get_captions(self, broadcast_id: str) -> List[Cue]:
        url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}/captions"
        json_captions = self._send_and_check("GET", url)
        if len(json_captions) == 0:
            raise NoCaptionsError("No captions found.")
        elif len(json_captions) > 1:
            raise ValueError(
                "Multiple captions found. Are some captions currently being published?"
            )
        else:
            json_captions = json_captions[0]
            if json_captions["status"] != "completed":
                raise NoCaptionsError("The captions are not ready yet.")
            if (
                "cues" not in json_captions
                or json_captions["cues"] is None
                or len(json_captions["cues"]) == 0
            ):
                raise NoCaptionsError("The cues are missing.")
            cues = [
                Cue(
                    id=str(i),
                    start=timedelta(seconds=c["start_time"]),
                    end=timedelta(seconds=c["end_time"]),
                    text=c["text"],
                    confidence=float(c["confidence"]),
                )
                for i, c in enumerate(json_captions["cues"], start=1)
            ]
            return cues

    def download_captions(self, broadcast_id: str, path: Path) -> None:
        cues = self.get_captions(broadcast_id=broadcast_id)
        captions.save(cues, path)

    def _get_captions_id(self, broadcast_id: str) -> str:
        url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}/captions"
        json_captions = self._send_and_check("GET", url)
        if len(json_captions) == 0:
            raise ValueError("No captions found.")
        else:
            return json_captions[0]["id"]

    def upload_captions(
        self,
        broadcast_id: str,
        path: Path,
        cancellation_token: Optional[CancellationToken],
        wait: bool = True,
    ) -> None:
        captions_id = self._get_captions_id(broadcast_id=broadcast_id)
        self._upload_captions(
            broadcast_id=broadcast_id, captions_id=captions_id, path=path
        )
        if wait:
            self._wait_for_captions_publish(
                broadcast_id=broadcast_id,
                captions_id=captions_id,
                cancellation_token=cancellation_token,
            )

    def _upload_captions(self, broadcast_id: str, captions_id: str, path: Path) -> None:
        url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}/captions/{captions_id}"
        cues = [
            {
                "start_time": c.start.total_seconds(),
                "end_time": c.end.total_seconds(),
                "text": c.text,
                # BoxCast seems to default to 1 when uploading via UI
                "confidence": c.confidence if c.confidence is not None else 1,
            }
            for c in captions.load(path)
        ]
        payload = {"cues": cues, "publish_status": "publishing"}
        self._send_and_check("PUT", url, json=payload)

    def _wait_for_captions_publish(
        self,
        broadcast_id: str,
        captions_id: str,
        cancellation_token: Optional[CancellationToken],
        timeout: timedelta = timedelta(minutes=5),
    ) -> None:
        start = datetime.now()
        while (datetime.now() - start) < timeout:
            url = f"{self._config.boxcast_base_url}/account/broadcasts/{broadcast_id}/captions/{captions_id}"
            json_captions = self._send_and_check("GET", url)
            status = json_captions["publish_status"]
            if status == "published":
                return
            else:
                autochecklist.sleep_attentively(
                    self._config.upload_captions_retry_delay,
                    cancellation_token=cancellation_token,
                )
        self._messenger.log_problem(
            ProblemLevel.WARN,
            f"The captions have still not been published after {timeout.total_seconds()} seconds."
            " Please check their status on BoxCast.",
        )

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
            if self._config.boxcast_verbose_logging:
                try:
                    self._log_request(
                        response=response,
                        method=method,
                        url=url,
                        params=params,
                        body=json,
                        headers=headers,
                    )
                except Exception as e:
                    self._messenger.log_problem(
                        ProblemLevel.WARN,
                        f"Failed to log request to {method} {url}: {e}.",
                        stacktrace=traceback.format_exc(),
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

    def _log_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        response: Response,
        params: Optional[Mapping[str, str]] = None,
        body: Optional[Mapping[str, object]] = None,
    ) -> None:
        # Just in case
        headers = headers | {"Authorization": "[CENSORED]"}
        t = datetime.now().strftime("%Y%m%d-%H%M%S")
        url_path = urlparse(url).path.removeprefix("/")
        p = self._config.log_dir.joinpath(
            f"{t}_boxcast_{method.lower()}_{url_path.replace('/', '_')}.jsonc"
        )
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"// {method} {url}\n")
            f.write(f"// REQUEST PARAMS:\n")
            if params is not None:
                for k, v in params.items():
                    f.write(f"//   * {k} = {v}\n")
            f.write(f"// REQUEST HEADERS:\n")
            for k, v in headers.items():
                f.write(f"//   * {k}: {v}\n")
            f.write(f"// RESPONSE STATUS: {response.status_code}\n")
            f.write(f"// RESPONSE HEADERS:\n")
            for k, v in response.headers.items():
                f.write(f"//   * {k}: {v}\n")
            json.dump({"request": body, "response": response.json()}, f, indent=2)

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
