from __future__ import annotations

import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import autochecklist
from autochecklist import CancellationToken, Messenger, ProblemLevel, TaskStatus
from config import Config
from requests import Response
from vimeo.client import VimeoClient

from .credentials import Credential, CredentialStore, InputPolicy


class ReccVimeoClient:
    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        config: Config,
        cancellation_token: Optional[CancellationToken],
        lazy_login: bool = False,
    ):
        self._messenger = messenger
        self._credential_store = credential_store
        self._cfg = config

        if not lazy_login:
            self._client = self._login_with_retries(
                max_attempts=3, cancellation_token=cancellation_token
            )

    def get(self, url: str, params: Optional[Dict[str, Any]]) -> Response:
        return self._client.get(url, params=params, timeout=self._cfg.timeout_seconds)

    def post(self, url: str, data: Union[None, bytes, Dict[str, Any]]) -> Response:
        return self._client.post(url, data=data, timeout=self._cfg.timeout_seconds)

    def put(self, url: str, data: Union[None, bytes, Dict[str, Any]]) -> Response:
        return self._client.put(url, data=data, timeout=self._cfg.timeout_seconds)

    def patch(self, url: str, data: Union[None, bytes, Dict[str, Any]]) -> Response:
        return self._client.patch(url, data=data, timeout=self._cfg.timeout_seconds)

    def _login_with_retries(
        self, max_attempts: int, cancellation_token: Optional[CancellationToken]
    ) -> VimeoClient:
        self._messenger.log_status(
            TaskStatus.RUNNING,
            f"Connecting to the Vimeo API...",
        )
        for attempt_num in range(1, max_attempts + 1):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            credentials = self._credential_store.get_multiple(
                prompt="Enter the Vimeo credentials.",
                credentials=[
                    Credential.VIMEO_ACCESS_TOKEN,
                    Credential.VIMEO_CLIENT_ID,
                    Credential.VIMEO_CLIENT_SECRET,
                ],
                request_input=(
                    InputPolicy.ALWAYS if attempt_num > 1 else InputPolicy.AS_REQUIRED
                ),
            )
            access_token = credentials[Credential.VIMEO_ACCESS_TOKEN]
            client_id = credentials[Credential.VIMEO_CLIENT_ID]
            client_secret = credentials[Credential.VIMEO_CLIENT_SECRET]
            client = VimeoClient(
                token=access_token,
                key=client_id,
                secret=client_secret,
            )
            response: Response = client.get(
                "/tutorial", params={}, timeout=self._cfg.timeout_seconds
            )
            if response.status_code == 200:
                self._messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Successfully connected to the Vimeo API.",
                )
                return client
            else:
                self._messenger.log_debug(
                    f"Vimeo client test request failed (attempt {attempt_num}/{max_attempts}). Response had HTTP status {response.status_code}.",
                )
        raise RuntimeError(
            f"Failed to connect to the Vimeo API ({max_attempts} attempts)"
        )

    def get_video_data(self, cancellation_token: CancellationToken) -> Tuple[str, str]:
        # Wait for the video to be posted
        while True:
            response = self.get(
                "/me/videos",
                params={
                    "fields": "created_time,uri,metadata.connections.texttracks.uri",
                    "per_page": 1,
                    "sort": "date",
                    "direction": "desc",
                },
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Vimeo client failed to access GET /videos (HTTP status {response.status_code})."
                )

            response_body = response.json()
            response_data = response.json()["data"][0]
            if response_body["total"] < 1 or (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(response_data["created_time"])
                > timedelta(hours=self._cfg.vimeo_new_video_hours)
            ):
                self._messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Video not yet found on Vimeo as of {datetime.now().strftime('%H:%M:%S')}. Retrying in {self._cfg.vimeo_retry_seconds} seconds.",
                )
                autochecklist.sleep_attentively(
                    timedelta(seconds=self._cfg.vimeo_retry_seconds), cancellation_token
                )
            else:
                self._messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Found newly-uploaded Vimeo video at URI '{response_data['uri']}'.",
                )
                break

        video_uri = response_data["uri"]
        texttrack_uri = response_data["metadata"]["connections"]["texttracks"]["uri"]
        return (video_uri, texttrack_uri)

    def disable_automatic_captions(
        self, texttracks_uri: str, cancellation_token: CancellationToken
    ):
        response = self.get(texttracks_uri, params={"fields": "uri,name"})

        if response.status_code != 200:
            raise RuntimeError(
                f"The Vimeo client failed to get the text tracks for today's video. GET {texttracks_uri} returned HTTP status {response.status_code}."
            )

        response_data = response.json()["data"]
        for texttrack in response_data:
            cancellation_token.raise_if_cancelled()
            # If we wanted to be sure we weren't disabling captions we want to
            # keep, we could check that the language field contains "autogen."
            # That probably isn't necessary as long as this task is performed
            # before our captions are uploaded and there are never existing
            # captions we want to keep.
            try:
                patch_uri = texttrack["uri"]
                patch_response = self.patch(patch_uri, data={"active": False})

                if patch_response.status_code != 200:
                    raise RuntimeError(
                        f"PATCH {patch_uri} returned HTTP status {patch_response.status_code}."
                    )
                self._messenger.log_debug(
                    f"Disabled autogenerated text track '{texttrack['name']}' at '{patch_uri}'."
                )
            # Catch exceptions instead of just moving this log statement into the
            # if statement so that, if the client itself throws an exception, it
            # gets caught.
            except Exception as e:
                self._messenger.log_problem(
                    ProblemLevel.WARN,
                    f"The Vimeo client failed to disable text track '{texttrack['name']}' at '{texttrack['uri']}' due to an error: {e}",
                    stacktrace=traceback.format_exc(),
                )

    def rename_video(self, video_uri: str, new_title: str):
        response = self.patch(
            video_uri,
            data={"name": new_title},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Vimeo client failed to rename video (HTTP status {response.status_code})."
            )

    def upload_captions_to_vimeo(self, final_captions_file: Path, texttrack_uri: str):
        # See https://developer.vimeo.com/api/upload/texttracks

        # (1) Get text track URI: done in get_vimeo_video_data()

        # (2) Get upload link for text track
        (upload_link, uri) = self._get_vimeo_texttrack_upload_link(texttrack_uri)
        self._messenger.log_status(
            TaskStatus.RUNNING,
            f"Found the text track upload link and URI for the Vimeo video.",
        )

        # (3) Upload text track
        self._upload_texttrack(final_captions_file, upload_link)
        self._messenger.log_status(
            TaskStatus.RUNNING, "Uploaded the text track for the Vimeo video."
        )

        # (4) Mark text track as active
        self._activate_texttrack(uri)
        self._messenger.log_status(
            TaskStatus.RUNNING,
            "Marked the newly-uploaded text track for the Vimeo video as active.",
        )

    def _get_vimeo_texttrack_upload_link(self, texttrack_uri: str) -> Tuple[str, str]:
        response = self.post(
            texttrack_uri,
            data={
                "type": self._cfg.vimeo_captions_type,
                "language": self._cfg.vimeo_captions_language,
                "name": self._cfg.vimeo_captions_name,
            },
        )

        status_code = response.status_code
        if status_code != 201:
            raise RuntimeError(
                f"Failed to get text track upload link for Vimeo video (HTTP status {status_code})."
            )

        response_body = response.json()
        return (response_body["link"], response_body["uri"])

    def _upload_texttrack(self, final_captions_file: Path, upload_link: str):
        # Read the captions from final.vtt
        # If you don't set the encoding to UTF-8, then Unicode characters get mangled
        with open(final_captions_file, "r", encoding="utf-8") as f:
            vtt = f.read()

        # If you don't encode the VTT file as UTF-8, then for some reason some characters get dropped at the end of the
        # file (if there are Unicode characters)
        response = self.put(upload_link, data=vtt.encode("utf-8"))

        status_code = response.status_code
        if status_code != 200:
            raise RuntimeError(
                f"Failed to upload text track for Vimeo video (HTTP status {status_code})"
            )

    def _activate_texttrack(self, texttrack_uri: str):
        response = self.patch(texttrack_uri, data={"active": True})

        status_code = response.status_code
        if status_code != 200:
            raise RuntimeError(
                f"Failed to mark text track at link '{texttrack_uri}' as active (HTTP status {status_code})."
            )
