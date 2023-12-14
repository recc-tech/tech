"""
Code for interacting with the Planning Center Services API.
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import requests
from autochecklist import CancellationToken, Messenger
from common.credentials import Credential, CredentialStore, InputPolicy
from requests.auth import HTTPBasicAuth


@dataclass(frozen=True)
class Plan:
    id: str
    title: str
    series_title: str


@dataclass(frozen=True)
class Attachment:
    id: str
    filename: str
    content_type: str


class PlanningCenterClient:
    _BASE_URL = "https://api.planningcenteronline.com"
    _SERVICES_BASE_URL = f"{_BASE_URL}/services/v2"
    _SUNDAY_GATHERINGS_SERVICE_TYPE_ID = "882857"
    _TIMEOUT_SECONDS = 60.0

    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        lazy_login: bool = False,
    ):
        self._messenger = messenger
        self._credential_store = credential_store

        if not lazy_login:
            self._test_credentials(max_attempts=3)

    def find_plan_by_date(
        self, dt: date, service_type: str = _SUNDAY_GATHERINGS_SERVICE_TYPE_ID
    ) -> Plan:
        today_str = dt.strftime("%Y-%m-%d")
        tomorrow_str = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        response = requests.get(
            url=f"{self._SERVICES_BASE_URL}/service_types/{service_type}/plans",
            params={
                "filter": "before,after",
                "before": tomorrow_str,
                "after": today_str,
            },
            auth=self._get_auth(),
            timeout=self._TIMEOUT_SECONDS,
        )
        if response.status_code // 100 != 2:
            raise ValueError(f"Request failed with status code {response.status_code}")
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
        self, plan_id: str, service_type: str = _SUNDAY_GATHERINGS_SERVICE_TYPE_ID
    ) -> str:
        app_id, secret = self._get_auth()
        response = requests.get(
            url=f"{self._SERVICES_BASE_URL}/service_types/{service_type}/plans/{plan_id}/items",
            params={"per_page": 100},
            auth=HTTPBasicAuth(app_id, secret),
            timeout=self._TIMEOUT_SECONDS,
        )
        if response.status_code // 100 != 2:
            raise ValueError(f"Request failed with status code {response.status_code}")
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
        self, plan_id: str, service_type: str = _SUNDAY_GATHERINGS_SERVICE_TYPE_ID
    ) -> Set[Attachment]:
        app_id, secret = self._get_auth()
        response = requests.get(
            url=f"{self._SERVICES_BASE_URL}/service_types/{service_type}/plans/{plan_id}/attachments",
            params={"per_page": 100},
            auth=HTTPBasicAuth(app_id, secret),
            timeout=self._TIMEOUT_SECONDS,
        )
        if response.status_code // 100 != 2:
            raise ValueError(f"Request failed with status code {response.status_code}")
        attachments_json = response.json()["data"]
        return {
            Attachment(
                id=a["id"],
                filename=a["attributes"]["filename"],
                content_type=a["attributes"]["content_type"],
            )
            for a in attachments_json
        }

    async def download_attachments(
        self,
        downloads: List[Tuple[Attachment, Path]],
        cancellation_token: Optional[CancellationToken],
    ):
        app_id, secret = self._get_auth()
        auth = aiohttp.BasicAuth(login=app_id, password=secret)
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._download_one_asset(
                    attachment, destination, session, auth, cancellation_token
                )
                for attachment, destination in downloads
            ]
            await asyncio.gather(*tasks)
        # Avoid RuntimeWarnings for unclosed resources
        # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
        await asyncio.sleep(0.25)

    def _test_credentials(self, max_attempts: int):
        for attempt_num in range(1, max_attempts + 1):
            url = f"{self._BASE_URL}/people/v2/me"
            response = requests.get(
                url, auth=self._get_auth(), timeout=self._TIMEOUT_SECONDS
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
        cancellation_token: Optional[CancellationToken],
    ) -> None:
        # Get URL for file contents
        link_url = f"{self._SERVICES_BASE_URL}/attachments/{attachment.id}/open"
        async with session.post(link_url, auth=auth) as response:
            if response.status // 100 != 2:
                raise ValueError(
                    f"Request to '{link_url}' for file '{destination.name}' failed with status {response.status}."
                )
            response_json = await response.json()
            file_contents_url = response_json["data"]["attributes"]["attachment_url"]

        # Get actual data
        async with session.get(file_contents_url) as response:
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
            except BaseException:
                # Don't leave behind partially-downloaded files
                destination.unlink(missing_ok=True)
                raise
