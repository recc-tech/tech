from __future__ import annotations

import asyncio
import filecmp
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Literal, Optional, Set, Union

from autochecklist import Messenger, ProblemLevel, TaskStatus
from config import Config
from external_services import Attachment, FileType, PlanningCenterClient


class SkipCondition(Enum):
    """Conditions under which an asset download should be skipped"""

    NEVER = auto()
    """Never skip."""
    IF_FILENAME_EXISTS = auto()
    """Skip this file if a file with the same name already exists."""
    ALWAYS = auto()
    """Always skip."""


class Action(Enum):
    OK = auto()
    """Don't do anything because there's no problem."""
    WARN = auto()
    """Emit a warning."""
    ERROR = auto()
    """Raise an error."""

    @staticmethod
    def parse(s: Literal["ok", "warn", "error"]) -> Action:
        match s:
            case "ok":
                return Action.OK
            case "warn":
                return Action.WARN
            case "error":
                return Action.ERROR


@dataclass(frozen=True)
class AssetCategory:
    """
    Download settings for a category of assets (e.g., announcements, images)
    """

    name: str
    """User-friendly category name"""
    skip: SkipCondition
    """When to skip downloading"""
    file_type: FileType
    """Expected file type for assets in this category"""
    filename_regex: str
    """
    Regular expression for the filename.
    The regex will be used in case-insensitive mode.
    """
    target_dir: Path
    """Directory to download the assets into"""
    append_date: bool
    """If `True`, then today's date will be appended to the filename."""
    deduplicate: bool
    """
    If `True`, then the asset will be deleted after download if it is found to
    match any other files.
    If `True` and there are multiple files on Planning Center which are
    identical to one another, only one will be kept.
    If `False`, then the asset will not be deleted after download.
    """
    overwrite_existing: bool
    """
    If `True`, then existing files with the same name will be overwritten.
    """
    if_missing: Action
    """What to do in case no assets fall into this category."""
    if_many: Action
    """What to do in case multiple assets fall into this category"""

    def matches(self, a: Attachment) -> bool:
        return a.file_type == self.file_type and bool(
            re.search(self.filename_regex, a.filename, re.IGNORECASE)
        )


@dataclass
class Download:
    destination: Path
    is_required: bool
    deduplicate: bool


class DownloadResult:
    pass


@dataclass
class DownloadSkipped(DownloadResult):
    reason: str

    def __str__(self) -> str:
        return f"Not downloaded (reason: {self.reason})"


@dataclass
class DownloadFailed(DownloadResult):
    exc: BaseException

    def __str__(self) -> str:
        return f"Download failed: {self.exc} ({type(self.exc).__name__})"


@dataclass
class DownloadSucceeded(DownloadResult):
    destination: Path

    def __str__(self) -> str:
        return f"Successfully downloaded to {self.destination.resolve().as_posix()}"


@dataclass
class DownloadDeduplicated(DownloadResult):
    original: Path

    def __str__(self) -> str:
        return f"Duplicate of {self.original.resolve().as_posix()}"


@dataclass
class DownloadPlan:
    downloads: Dict[Attachment, Union[Download, DownloadSkipped]]


class AssetManager:
    _VIDEO_EXTENSIONS = {".mp4", ".mov"}

    def __init__(self, config: Config) -> None:
        self._config = config
        self._CATEGORIES = [
            AssetCategory(
                name="livestream announcements video",
                skip=(
                    SkipCondition.NEVER
                    if config.download_announcements_vid
                    else SkipCondition.ALWAYS
                ),
                file_type=FileType.VIDEO,
                filename_regex=config.announcements_video_regex,
                target_dir=config.assets_by_service_dir,
                append_date=True,
                deduplicate=False,
                overwrite_existing=True,
                if_missing=Action.parse(config.if_announcements_vid_missing),
                if_many=Action.WARN,
            ),
            AssetCategory(
                name="kids video",
                skip=(
                    SkipCondition.NEVER
                    if config.download_kids_vid
                    else SkipCondition.ALWAYS
                ),
                file_type=FileType.VIDEO,
                filename_regex=config.kids_video_regex,
                target_dir=config.assets_by_service_dir,
                append_date=False,
                deduplicate=False,
                overwrite_existing=True,
                if_missing=Action.parse(config.if_kids_vid_missing),
                if_many=Action.WARN,
            ),
            AssetCategory(
                name="sermon notes",
                skip=(
                    SkipCondition.NEVER
                    if config.download_sermon_notes
                    else SkipCondition.ALWAYS
                ),
                file_type=FileType.DOCX,
                filename_regex=config.sermon_notes_regex,
                target_dir=config.assets_by_service_dir,
                append_date=False,
                deduplicate=False,
                overwrite_existing=True,
                if_missing=Action.parse(config.if_sermon_notes_missing),
                if_many=Action.WARN,
            ),
            AssetCategory(
                name="images",
                skip=SkipCondition.NEVER,
                file_type=FileType.IMAGE,
                filename_regex=".*",
                target_dir=config.images_dir,
                append_date=False,
                deduplicate=True,
                overwrite_existing=False,
                if_missing=Action.OK,
                if_many=Action.OK,
            ),
            AssetCategory(
                name="videos",
                skip=SkipCondition.IF_FILENAME_EXISTS,
                file_type=FileType.VIDEO,
                filename_regex=".*",
                target_dir=config.videos_dir,
                append_date=False,
                deduplicate=True,
                overwrite_existing=True,
                if_missing=Action.OK,
                if_many=Action.OK,
            ),
        ]
        kids_vid_category = [c for c in self._CATEGORIES if c.name == "kids video"]
        assert len(kids_vid_category) == 1
        self._KIDS_VID_CATEGORY = kids_vid_category[0]

    def locate_kids_video(self) -> Optional[Path]:
        def is_kids_video(p: Path) -> bool:
            pattern = self._config.kids_video_regex
            return (
                p.is_file()
                and p.suffix.lower() in self._VIDEO_EXTENSIONS
                and bool(re.search(pattern, p.stem, flags=re.IGNORECASE))
            )

        folder = self._config.assets_by_service_dir
        candidates = [p for p in folder.glob("*") if is_kids_video(p)]
        if len(candidates) == 1:
            return candidates[0]
        else:
            return None

    def locate_announcements_video(self) -> Optional[Path]:
        def is_announcements_video(p: Path) -> bool:
            pattern = self._config.announcements_video_regex
            return (
                p.is_file()
                and p.suffix.lower() in self._VIDEO_EXTENSIONS
                and bool(re.search(pattern, p.stem, flags=re.IGNORECASE))
            )

        folder = self._config.assets_by_service_dir
        candidates = [p for p in folder.glob("*") if is_announcements_video(p)]
        if len(candidates) == 1:
            return candidates[0]
        else:
            return None

    def download_pco_assets(
        self,
        client: PlanningCenterClient,
        messenger: Messenger,
    ) -> Dict[Attachment, DownloadResult]:
        plan = client.find_plan_by_date(self._config.start_time.date())
        attachments = client.find_attachments(plan.id)
        download_plan = self.plan_downloads(
            attachments=attachments,
            messenger=messenger,
        )
        return self.execute_plan(
            download_plan,
            pco_client=client,
            messenger=messenger,
        )

    def plan_downloads(
        self,
        attachments: Set[Attachment],
        messenger: Messenger,
    ) -> DownloadPlan:
        messenger.log_status(
            TaskStatus.RUNNING, "Looking for attachments in Planning Center."
        )
        today = self._config.start_time.date()
        category_by_attachment = {a: self._classify(a) for a in attachments}
        messenger.log_debug(
            f"{len(attachments)} attachments found on PCO: {category_by_attachment}"
        )
        # Sort so that results are deterministic, can be tested
        attachments_by_category = {
            cat: sorted(
                [a for (a, c) in category_by_attachment.items() if c == cat],
                key=lambda a: a.id,
            )
            for cat in self._CATEGORIES
        }
        downloads: Dict[Attachment, Union[Download, DownloadSkipped]] = {}

        for c in self._CATEGORIES:
            n = len(attachments_by_category[c])
            # Don't report a problem if the current station doesn't require
            # assets of this category anyway.
            if n == 0 and c.skip != SkipCondition.ALWAYS:
                _handle_missing(c, messenger)
            # Do give a warning for too many assets even if the current station
            # doesn't require these assets; it may be a sign that assets which
            # should be downloaded are being mis-classified.
            elif n > 1:
                _handle_many(n, c, messenger)
            for a in attachments_by_category[c]:
                s = _skip(a, c)
                if s is not None:
                    downloads[a] = s
                    continue
                filename = (
                    _append_date(a.filename, today) if c.append_date else a.filename
                )
                p = _find_available_path(
                    dest_dir=c.target_dir,
                    name=filename,
                    planned=_get_planned_paths(downloads),
                    overwrite=c.overwrite_existing,
                )
                downloads[a] = Download(
                    p,
                    is_required=c.if_missing == Action.ERROR,
                    deduplicate=c.deduplicate,
                )

        for a in attachments:
            if a not in downloads:
                downloads[a] = DownloadSkipped(reason="unknown attachment")

        for a in attachments_by_category[self._KIDS_VID_CATEGORY]:
            _check_kids_video_week_num(a, today, messenger)

        return DownloadPlan(downloads)

    def execute_plan(
        self,
        plan: DownloadPlan,
        pco_client: PlanningCenterClient,
        messenger: Messenger,
    ) -> Dict[Attachment, DownloadResult]:
        cancellation_token = messenger.allow_cancel()
        downloads = {
            a: d for (a, d) in plan.downloads.items() if isinstance(d, Download)
        }

        if len(downloads) == 0:
            messenger.log_problem(ProblemLevel.WARN, "No assets found to download.")
            return {
                a: d
                for (a, d) in plan.downloads.items()
                if isinstance(d, DownloadSkipped)
            }

        self._config.assets_by_service_dir.mkdir(exist_ok=True, parents=True)
        # Just in case
        self._config.videos_dir.mkdir(exist_ok=True, parents=True)
        self._config.images_dir.mkdir(exist_ok=True, parents=True)

        messenger.log_status(TaskStatus.RUNNING, "Downloading new assets.")
        results = asyncio.run(
            pco_client.download_attachments(
                {d.destination: a for (a, d) in downloads.items()},
                messenger,
                cancellation_token,
            )
        )

        ret: Dict[Attachment, DownloadResult] = {}
        for a, d in plan.downloads.items():
            if isinstance(d, DownloadSkipped):
                ret[a] = d
            elif d.destination not in results:
                ret[a] = DownloadSkipped("unknown reason")
            elif (e := results[d.destination]) is not None:
                ret[a] = DownloadFailed(e)
            else:
                ret[a] = DownloadSucceeded(d.destination)

        messenger.log_status(TaskStatus.RUNNING, "Removing duplicate assets.")
        for a, d in downloads.items():
            p = d.destination
            should_dedup = results.get(p, None) is None and d.deduplicate
            if should_dedup and (dup_of := _find_original(p)):
                ret[a] = DownloadDeduplicated(dup_of)
                p.unlink()

        messenger.log_status(TaskStatus.RUNNING, "Checking download results.")
        for a, d in downloads.items():
            if d.destination not in results:
                messenger.log_problem(
                    ProblemLevel.WARN,
                    f"The result of the download to '{d.destination.as_posix()}' is unknown.",
                )
            elif (exc := results[d.destination]) is not None:
                msg = f"Failed to download {a.filename}: {exc} ({type(exc).__name__})"
                if d.is_required:
                    raise Exception(msg)
                else:
                    messenger.log_problem(ProblemLevel.WARN, msg)

        return ret

    def _classify(self, attachment: Attachment) -> Optional[AssetCategory]:
        for c in self._CATEGORIES:
            if c.matches(attachment):
                return c
        return None


def _skip(a: Attachment, c: AssetCategory) -> Optional[DownloadSkipped]:
    match c.skip:
        case SkipCondition.ALWAYS:
            return DownloadSkipped(
                reason=f'assets in category "{c.name}" are not downloaded at this station'
            )
        case SkipCondition.NEVER:
            return None
        case SkipCondition.IF_FILENAME_EXISTS:
            p = c.target_dir.joinpath(a.filename)
            return (
                DownloadSkipped(reason=f"{p.as_posix()} already exists")
                if p.exists()
                else None
            )


def _append_date(filename: str, dt: date) -> str:
    stem = Path(filename).stem
    ext = Path(filename).suffix
    return f"{stem} {dt.strftime('%Y-%m-%d')}{ext}"


def _get_planned_paths(
    downloads: Dict[Attachment, Union[Download, DownloadSkipped]]
) -> Set[Path]:
    return {d.destination for d in downloads.values() if isinstance(d, Download)}


def _find_available_path(
    dest_dir: Path, name: str, planned: Set[Path], overwrite: bool
) -> Path:
    """
    Find a path for a new file that is not already used.
    If `overwrite = True`, then this function will ignore files that already
    exist in the destination directory (i.e., it will potentially overwrite
    them).
    Otherwise, it will choose a name that is not used by any existing file in
    the destination directory.
    In either case, the new path will not be in the `planned` set.
    """
    MAX_ATTEMPTS = 1000
    file = Path(name)
    suffix = file.suffix
    stem = file.stem
    for i in range(MAX_ATTEMPTS + 1):
        new_filepath = (
            dest_dir.joinpath(f"{stem}{suffix}")
            if i == 0
            else dest_dir.joinpath(f"{stem} ({i}){suffix}")
        )
        is_available = (
            overwrite or not new_filepath.exists()
        ) and new_filepath not in planned
        if is_available:
            return new_filepath
    raise ValueError(
        f"Failed to move {name} into {dest_dir.as_posix()} because no suitable name could be found (all attempted ones were already taken)."
    )


def _find_original(p: Path) -> Optional[Path]:
    directory = p.parent
    for other in directory.iterdir():
        if p.resolve() == other.resolve() or not other.is_file():
            continue
        if filecmp.cmp(p, other, shallow=False):
            return other
    return None


def _check_kids_video_week_num(
    video: Attachment, today: date, messenger: Messenger
) -> None:
    m = re.search(r"w(\d)", video.filename, flags=re.IGNORECASE)
    if not m:
        messenger.log_problem(
            ProblemLevel.WARN,
            "Unable to determine week number from Kids Connection video filename.",
        )
        return
    actual_num = int(m[1])
    expected_num = _get_week_num(today)
    if actual_num != expected_num:
        messenger.log_problem(
            ProblemLevel.WARN,
            f"The current week number is {expected_num}, but the Kids Connection video seems to be from week {actual_num}.",
        )
    else:
        messenger.log_debug(
            f"Kids Connection video is from week {actual_num}, as expected."
        )


def _get_week_num(day: date) -> int:
    for i in range(1, 5):
        d = day - timedelta(days=7 * i)
        if d.month != day.month:
            return i
    return 5


def _handle_missing(c: AssetCategory, messenger: Messenger) -> None:
    match c.if_missing:
        case Action.OK:
            pass
        case Action.WARN:
            messenger.log_problem(
                ProblemLevel.WARN, f'No attachments found for category "{c.name}".'
            )
        case Action.ERROR:
            raise ValueError(f'No attachments found for category "{c.name}".')


def _handle_many(n: int, c: AssetCategory, messenger: Messenger) -> None:
    match c.if_many:
        case Action.OK:
            pass
        case Action.WARN:
            messenger.log_problem(
                ProblemLevel.WARN, f'Found {n} attachments for category "{c.name}".'
            )
        case Action.ERROR:
            raise ValueError(f'Found {n} attachments for category "{c.name}".')
