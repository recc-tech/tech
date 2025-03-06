"""
Code for interacting with the Planning Center Services API.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, Set, Tuple, TypeVar

import aiohttp
import config
import requests
from aiohttp import ClientTimeout
from autochecklist import CancellationToken, Messenger
from config import Config
from requests.auth import HTTPBasicAuth

from .credentials import Credential, CredentialStore, InputPolicy

T = TypeVar("T")


@dataclass(frozen=True)
class Song:
    ccli: Optional[str]
    title: str
    author: Optional[str]


@dataclass(frozen=True)
class ItemNote:
    category: str
    contents: str


@dataclass(frozen=True)
class PlanItem:
    title: str
    description: str
    song: Optional[Song]
    notes: List[ItemNote]


@dataclass(frozen=True)
class PlanSection:
    title: str
    items: List[PlanItem]


@dataclass(frozen=True)
class Plan:
    id: str
    title: str
    series_title: str
    date: date
    web_page_url: str


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


class TeamMemberStatus(Enum):
    CONFIRMED = auto()
    UNCONFIRMED = auto()
    DECLINED = auto()

    @staticmethod
    def parse(s: str) -> TeamMemberStatus:
        match s.lower():
            case "c":
                return TeamMemberStatus.CONFIRMED
            case "u":
                return TeamMemberStatus.UNCONFIRMED
            case "d":
                return TeamMemberStatus.DECLINED
            case _:
                raise ValueError(f"Unknown status '{s}'")


@dataclass(frozen=True)
class TeamMember:
    name: str
    status: TeamMemberStatus


@dataclass(frozen=True)
class PresenterSet:
    speakers: List[TeamMember]
    hosts: List[TeamMember]


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
        service_type = service_type or self._cfg.pco_service_type_id
        today_str = dt.strftime("%Y-%m-%d")
        plans = self._send_and_check_status(
            url=f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans",
            params={
                "filter": "before,after",
                "before": (dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                "after": today_str,
            },
        )["data"]
        if len(plans) != 1:
            config_file = config.locate_global_config().as_posix()
            raise ValueError(
                f"Found {len(plans)} plans on {today_str}."
                f" If this is not a weekly 10:30 gathering, you may need to change the service type ID in {config_file}."
            )
        plan = plans[0]
        return Plan(
            id=plan["id"],
            title=plan["attributes"]["title"],
            series_title=plan["attributes"]["series_title"],
            date=dt,
            web_page_url=plan["attributes"]["planning_center_url"],
        )

    def find_plan_items(
        self,
        plan_id: str,
        include_songs: bool,
        include_item_notes: bool,
        service_type: Optional[str] = None,
    ) -> List[PlanSection]:
        service_type = service_type or self._cfg.pco_service_type_id
        params: Dict[str, object] = {"per_page": 200}
        include: List[str] = []
        if include_songs:
            include.append("song")
        if include_item_notes:
            include.append("item_notes")
        if include:
            params["include"] = ",".join(include)
        items_json = self._send_and_check_status(
            url=f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans/{plan_id}/items",
            params=params,
        )
        sections: List[PlanSection] = []
        current_section_title: str = "[[FAKE SECTION]]"
        current_section_items: List[PlanItem] = []
        for itm in items_json["data"]:
            if itm["attributes"]["item_type"] == "header":
                if current_section_title != "[[FAKE SECTION]]" or current_section_items:
                    sections.append(
                        PlanSection(
                            title=current_section_title,
                            items=current_section_items,
                        )
                    )
                current_section_title = itm["attributes"]["title"] or ""
                current_section_items = []
            else:
                item_title = str(itm["attributes"]["title"])
                song = _find_song(
                    itm, included=items_json["included"], default_title=item_title
                )
                notes = _find_notes(itm, included=items_json["included"])
                item = PlanItem(
                    title=item_title,
                    description=itm["attributes"]["description"] or "",
                    song=song,
                    notes=notes,
                )
                current_section_items.append(item)
        if current_section_title != "[[FAKE SECTION]]" or current_section_items:
            sections.append(
                PlanSection(title=current_section_title, items=current_section_items)
            )
        return sections

    def find_message_notes(
        self, plan_id: str, service_type: Optional[str] = None
    ) -> str:
        sections = self.find_plan_items(
            plan_id=plan_id,
            service_type=service_type,
            include_songs=False,
            include_item_notes=False,
        )
        message_items = [
            i
            for s in sections
            for i in s.items
            if re.match("message title:", i.title, re.IGNORECASE)
        ]
        if len(message_items) != 1:
            raise ValueError(
                f"Found {len(message_items)} plan items which look like message notes."
            )
        return message_items[0].description

    def find_attachments(
        self, plan_id: str, service_type: Optional[str] = None
    ) -> Set[Attachment]:
        service_type = service_type or self._cfg.pco_service_type_id
        attachments_json = self._send_and_check_status(
            url=f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans/{plan_id}/attachments",
            params={"per_page": 100},
        )["data"]
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
            app_id, secret = self._get_auth(force_input=False)
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
        service_type = service_type or self._cfg.pco_service_type_id
        people = self._send_and_check_status(
            url=f"{self._cfg.pco_services_base_url}/service_types/{service_type}/plans/{plan_id}/team_members",
            params={"filter": "not_declined"},
        )["data"]
        speakers = [
            TeamMember(
                name=p["attributes"]["name"],
                status=TeamMemberStatus.parse(p["attributes"]["status"]),
            )
            for p in people
            if p["attributes"]["team_position_name"].lower() == "speaker"
        ]
        hosts = [
            TeamMember(
                name=p["attributes"]["name"],
                status=TeamMemberStatus.parse(p["attributes"]["status"]),
            )
            for p in people
            if p["attributes"]["team_position_name"].lower() == "mc host"
        ]
        return PresenterSet(speakers=speakers, hosts=hosts)

    def _test_credentials(self, max_attempts: int):
        url = f"{self._cfg.pco_base_url}/people/v2/me"
        for attempt_num in range(1, max_attempts + 1):
            response = self._send(url=url, params={}, force_auth=attempt_num > 1)
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

    def _send(
        self, url: str, params: Dict[str, object], force_auth: bool
    ) -> requests.Response:
        app_id, secret = self._get_auth(force_input=force_auth)
        return requests.get(
            url=url,
            params=params,  # pyright: ignore[reportArgumentType]
            auth=HTTPBasicAuth(app_id, secret),
            timeout=self._cfg.timeout_seconds,
        )

    def _send_and_check_status(self, url: str, params: Dict[str, object]) -> Any:
        response = self._send(url=url, params=params, force_auth=False)
        if response.status_code // 100 != 2:
            raise ValueError(
                f"Request to {url} failed with status code {response.status_code}"
            )
        return response.json()

    def _get_auth(self, force_input: bool) -> Tuple[str, str]:
        credentials = self._credential_store.get_multiple(
            prompt="Enter the Planning Center credentials.",
            credentials=[
                Credential.PLANNING_CENTER_APP_ID,
                Credential.PLANNING_CENTER_SECRET,
            ],
            request_input=(
                InputPolicy.ALWAYS if force_input else InputPolicy.AS_REQUIRED
            ),
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


@dataclass
class Maybe(Generic[T]):
    data: Optional[T]

    def bind(self, f: Callable[[T], T]) -> Maybe[T]:
        if self.data is None:
            return self
        else:
            return Maybe(f(self.data))


def _get(d: Any, key: str) -> Maybe[Any]:
    """
    Make a series of accesses to a series of nested dictionaries, but check for
    `None` at each step.
    """
    keys = key.split(".")
    m = Maybe(d)
    for k in keys:
        m = m.bind(lambda d: d[k] if k in d else None)
    return m


def _find_song(itm: Any, included: List[Any], default_title: str) -> Optional[Song]:
    song_id = _get(itm, "relationships.song.data.id").data
    matching_songs = [i for i in included if i["type"] == "Song" and i["id"] == song_id]
    song_json = None if not song_id or len(matching_songs) == 0 else matching_songs[0]

    def make_song(s: Any) -> Song:
        return Song(
            ccli=_get(s, "attributes.ccli_number").bind(lambda s: str(s)).data,
            title=_get(s, "attributes.title").bind(lambda s: str(s)).data
            or default_title,
            author=_get(s, "attributes.author").bind(lambda s: str(s)).data,
        )

    song = Maybe(song_json).bind(make_song)
    return song.data


def _find_notes(itm: Any, included: List[Any]) -> List[ItemNote]:
    note_ids: List[int] = (
        _get(itm, "relationships.item_notes.data")
        .bind(lambda d: [x["id"] for x in d])
        .data
        or []
    )
    matching_notes = [
        i
        for i in included
        if _get(i, "type").data == "ItemNote" and _get(i, "id").data in note_ids
    ]
    return [
        ItemNote(
            category=_get(n, "attributes.category_name").data or "",
            contents=_get(n, "attributes.content").data or "",
        )
        for n in matching_notes
    ]
