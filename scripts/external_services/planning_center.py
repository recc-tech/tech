"""
Code for interacting with the Planning Center Services API.
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import requests
from aiohttp import ClientTimeout
from autochecklist import CancellationToken, Messenger
from config import Config
from requests.auth import HTTPBasicAuth

from .credentials import Credential, CredentialStore, InputPolicy


@dataclass(frozen=True)
class Plan:
    id: str
    title: str
    series_title: str


class FileType(Enum):
    VIDEO = auto()
    IMAGE = auto()
    DOCX = auto()
    OTHER = auto()


_DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@dataclass(frozen=True)
class Attachment:
    id: str
    filename: str
    num_bytes: int
    pco_filetype: str
    mime_type: str

    @property
    def file_type(self) -> FileType:
        if self.pco_filetype.lower() == "video":
            return FileType.VIDEO
        elif self.pco_filetype.lower() == "image":
            return FileType.IMAGE
        elif self.mime_type.lower() == _DOCX_MIME_TYPE:
            return FileType.DOCX
        else:
            return FileType.OTHER


@dataclass(frozen=True)
class PresenterSet:
    speaker_names: List[str]
    mc_host_names: List[str]


class PlanningCenterClient:
    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        config: Config,
        lazy_login: bool = False,
    ):
        self._messenger = messenger
        self._credential_store = credential_store
        self._cfg = config

        if not lazy_login:
            self._test_credentials(max_attempts=3)

    def find_plan_by_date(self, dt: date, service_type: Optional[str] = None) -> Plan:
        service_type = service_type or self._cfg.pco_sunday_service_type_id
        today_str = dt.strftime("%Y-%m-%d")
        tomorrow_str = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        url = f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans"
        response = requests.get(
            url=url,
            params={
                "filter": "before,after",
                "before": tomorrow_str,
                "after": today_str,
            },
            auth=self._get_auth(),
            timeout=self._cfg.timeout_seconds,
        )
        if response.status_code // 100 != 2:
            raise ValueError(
                f"Request to {url} failed with status code {response.status_code}"
            )
        plans = response.json()["data"]
        if len(plans) != 1:
            raise ValueError(f"Found {len(plans)} plans on {today_str}.")
        plan = plans[0]
        return Plan(
            id=plan["id"],
            title=plan["attributes"]["title"],
            series_title=plan["attributes"]["series_title"],
        )

    def find_message_notes(
        self, plan_id: str, service_type: Optional[str] = None
    ) -> str:
        service_type = service_type or self._cfg.pco_sunday_service_type_id
        app_id, secret = self._get_auth()
        url = f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans/{plan_id}/items"
        response = requests.get(
            url=url,
            params={"per_page": 100},
            auth=HTTPBasicAuth(app_id, secret),
            timeout=self._cfg.timeout_seconds,
        )
        if response.status_code // 100 != 2:
            raise ValueError(
                f"Request to {url} failed with status code {response.status_code}"
            )
        items = response.json()["data"]

        def is_message_notes_item(item: Dict[str, Any]) -> bool:
            if "attributes" not in item:
                return False
            if "title" not in item["attributes"] or not re.fullmatch(
                "^message title:.*", item["attributes"]["title"], re.IGNORECASE
            ):
                return False
            return True

        message_items = [itm for itm in items if is_message_notes_item(itm)]
        if len(message_items) != 1:
            raise ValueError(
                f"Found {len(message_items)} plan items which look like message notes."
            )
        return message_items[0]["attributes"]["description"]

    def find_attachments(
        self, plan_id: str, service_type: Optional[str] = None
    ) -> Set[Attachment]:
        service_type = service_type or self._cfg.pco_sunday_service_type_id
        app_id, secret = self._get_auth()
        url = f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans/{plan_id}/attachments"
        response = requests.get(
            url=url,
            params={"per_page": 100},
            auth=HTTPBasicAuth(app_id, secret),
            timeout=self._cfg.timeout_seconds,
        )
        if response.status_code // 100 != 2:
            raise ValueError(
                f"Request to {url} failed with status code {response.status_code}"
            )
        attachments_json = response.json()["data"]
        return {
            Attachment(
                id=a["id"],
                filename=a["attributes"]["filename"],
                num_bytes=a["attributes"]["file_size"],
                pco_filetype=a["attributes"]["filetype"],
                mime_type=a["attributes"]["content_type"],
            )
            for a in attachments_json
        }

    async def download_attachments(
        self,
        downloads: Dict[Path, Attachment],
        messenger: Messenger,
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[Path, Optional[BaseException]]:
        """
        Downloads each attachment to the corresponding path. Returns a dict
        containing, for each path, `None` if the attachment was downloaded
        successfully and an exception otherwise.
        """
        results: List[Optional[BaseException]]
        downloads_list = list(downloads.items())
        paths = [p for (p, _) in downloads_list]
        try:
            app_id, secret = self._get_auth()
            auth = aiohttp.BasicAuth(login=app_id, password=secret)
            async with aiohttp.ClientSession() as session:
                tasks = [
                    self._download_one_asset(
                        attachment,
                        destination,
                        session,
                        auth,
                        messenger,
                        cancellation_token,
                    )
                    for destination, attachment in downloads_list
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
        except BaseException as e:
            results = [e for _ in downloads]
        # Avoid RuntimeWarnings for unclosed resources
        # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
        await asyncio.sleep(0.25)
        return {p: r for (p, r) in zip(paths, results)}

    def find_presenters(
        self, plan_id: str, service_type: Optional[str] = None
    ) -> PresenterSet:
        service_type = service_type or self._cfg.pco_sunday_service_type_id
        app_id, secret = self._get_auth()
        url = f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans/{plan_id}/team_members?filter=confirmed"
        response = requests.get(
            url=url,
            params={"filter": "confirmed"},
            auth=HTTPBasicAuth(app_id, secret),
            timeout=self._cfg.timeout_seconds,
        )
        if response.status_code // 100 != 2:
            raise ValueError(
                f"Request to {url} failed with status code {response.status_code}"
            )
        people = response.json()["data"]
        speaker_names = [
            p["attributes"]["name"]
            for p in people
            if p["attributes"]["team_position_name"].lower() == "speaker"
        ]
        mc_host_names = [
            p["attributes"]["name"]
            for p in people
            if p["attributes"]["team_position_name"].lower() == "mc host"
        ]
        return PresenterSet(speaker_names=speaker_names, mc_host_names=mc_host_names)

    def _test_credentials(self, max_attempts: int):
        for attempt_num in range(1, max_attempts + 1):
            url = f"{self._cfg.pco_base_url}/people/v2/me"
            response = requests.get(
                url, auth=self._get_auth(), timeout=self._cfg.timeout_seconds
            )
            if response.status_code // 100 == 2:
                return
            elif response.status_code == 401:
                self._messenger.log_debug(
                    f"Test request to GET {url} failed with status code {response.status_code} (attempt {attempt_num}/{max_attempts})."
                )
            else:
                raise ValueError(
                    f"Test request to GET {url} failed with status code {response.status_code}."
                )

    def _get_auth(self) -> Tuple[str, str]:
        credentials = self._credential_store.get_multiple(
            prompt="Enter the Planning Center credentials.",
            credentials=[
                Credential.PLANNING_CENTER_APP_ID,
                Credential.PLANNING_CENTER_SECRET,
            ],
            request_input=InputPolicy.AS_REQUIRED,
        )
        app_id = credentials[Credential.PLANNING_CENTER_APP_ID]
        secret = credentials[Credential.PLANNING_CENTER_SECRET]
        return (app_id, secret)

    async def _download_one_asset(
        self,
        attachment: Attachment,
        destination: Path,
        session: aiohttp.ClientSession,
        auth: aiohttp.BasicAuth,
        messenger: Messenger,
        cancellation_token: Optional[CancellationToken],
    ) -> None:
        key = messenger.create_progress_bar(
            display_name=attachment.filename,
            max_value=attachment.num_bytes / 1_000_000,
            units="MB",
        )
        downloaded_bytes = 0
        try:
            # Get URL for file contents
            link_url = (
                f"{self._cfg.pco_services_base_url}/attachments/{attachment.id}/open"
            )
            async with session.post(link_url, auth=auth) as response:
                if response.status // 100 != 2:
                    raise ValueError(
                        f"Request to '{link_url}' for file '{destination.name}' failed with status {response.status}."
                    )
                response_json = await response.json()
                file_contents_url = response_json["data"]["attributes"][
                    "attachment_url"
                ]

            # Get actual data
            # Increase the timeout because we often read large videos
            timeout = ClientTimeout(total=30 * 60)
            async with session.get(file_contents_url, timeout=timeout) as response:
                if response.status // 100 != 2:
                    raise ValueError(
                        f"Request to '{file_contents_url}' for file '{destination.name}' failed with status {response.status}."
                    )
                try:
                    with open(destination, "wb") as f:
                        async for data, _ in response.content.iter_chunks():
                            if cancellation_token:
                                cancellation_token.raise_if_cancelled()
                            f.write(data)
                            downloaded_bytes += len(data)
                            messenger.update_progress_bar(
                                key, downloaded_bytes / 1_000_000
                            )
                except BaseException:
                    # Don't leave behind partially-downloaded files
                    destination.unlink(missing_ok=True)
                    raise
        finally:
            messenger.delete_progress_bar(key)
