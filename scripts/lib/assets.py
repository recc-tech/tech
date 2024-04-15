import asyncio
import filecmp
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Optional, Union

from autochecklist import Messenger, ProblemLevel, TaskStatus
from config import Config
from external_services import Attachment, FileType, PlanningCenterClient


class AssetCategory(Enum):
    ANNOUNCEMENTS = auto()
    KIDS_VIDEO = auto()
    SERMON_NOTES = auto()
    IMAGE = auto()
    VIDEO = auto()
    UNKNOWN = auto()


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


class AssetManager:
    _VIDEO_EXTENSIONS = {".mp4", ".mov"}

    def __init__(self, config: Config) -> None:
        self._config = config

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
        *,
        download_kids_video: bool,
        download_notes_docx: bool,
        require_announcements: bool,
        dry_run: bool,
    ) -> Dict[Attachment, DownloadResult]:
        cancellation_token = messenger.allow_cancel()

        download_plan = self._plan_downloads(
            client=client,
            messenger=messenger,
            download_kids_video=download_kids_video,
            download_notes_docx=download_notes_docx,
            require_announcements=require_announcements,
        )
        downloads = {
            a: d for (a, d) in download_plan.items() if isinstance(d, Download)
        }

        if len(downloads) == 0:
            messenger.log_problem(ProblemLevel.WARN, "No assets found to download.")
            return {
                a: d
                for (a, d) in download_plan.items()
                if isinstance(d, DownloadSkipped)
            }
        if dry_run:
            messenger.log_debug("Skipping downloading assets: dry run.")
            return {
                a: (
                    d
                    if isinstance(d, DownloadSkipped)
                    else DownloadSucceeded(d.destination)
                )
                for (a, d) in download_plan.items()
            }

        self._config.assets_by_service_dir.mkdir(exist_ok=True, parents=True)
        # Just in case
        self._config.videos_dir.mkdir(exist_ok=True, parents=True)
        self._config.images_dir.mkdir(exist_ok=True, parents=True)

        messenger.log_status(TaskStatus.RUNNING, "Downloading new assets.")
        results = asyncio.run(
            client.download_attachments(
                {d.destination: a for (a, d) in downloads.items()},
                messenger,
                cancellation_token,
            )
        )

        ret: Dict[Attachment, DownloadResult] = {}
        for a, d in download_plan.items():
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

    def _classify(self, attachment: Attachment) -> AssetCategory:
        is_announcement = attachment.file_type == FileType.VIDEO and bool(
            re.search(
                self._config.announcements_video_regex,
                attachment.filename,
                re.IGNORECASE,
            )
        )
        if is_announcement:
            return AssetCategory.ANNOUNCEMENTS
        is_kids_video = attachment.file_type == FileType.VIDEO and bool(
            re.search(self._config.kids_video_regex, attachment.filename, re.IGNORECASE)
        )
        if is_kids_video:
            return AssetCategory.KIDS_VIDEO
        is_sermon_notes = attachment.file_type == FileType.DOCX and bool(
            re.search(
                self._config.sermon_notes_regex, attachment.filename, re.IGNORECASE
            )
        )
        if is_sermon_notes:
            return AssetCategory.SERMON_NOTES
        if attachment.file_type == FileType.IMAGE:
            return AssetCategory.IMAGE
        if attachment.file_type == FileType.VIDEO:
            return AssetCategory.VIDEO
        return AssetCategory.UNKNOWN

    def _plan_downloads(
        self,
        client: PlanningCenterClient,
        messenger: Messenger,
        download_kids_video: bool,
        download_notes_docx: bool,
        require_announcements: bool,
    ) -> Dict[Attachment, Union[Download, DownloadSkipped]]:
        messenger.log_status(
            TaskStatus.RUNNING, "Looking for attachments in Planning Center."
        )
        today = self._config.start_time.date()
        plan = client.find_plan_by_date(today)
        attachments = client.find_attachments(plan.id)
        category_by_attachment = {a: self._classify(a) for a in attachments}
        messenger.log_debug(
            f"{len(attachments)} attachments found on PCO: {category_by_attachment}"
        )
        attachments_by_category = {
            cat: {a for (a, c) in category_by_attachment.items() if c == cat}
            for cat in AssetCategory
        }
        assets_by_service_dir = self._config.assets_by_service_dir
        downloads: Dict[Attachment, Union[Download, DownloadSkipped]] = {}

        sermon_notes = attachments_by_category[AssetCategory.SERMON_NOTES]
        if download_notes_docx:
            if len(sermon_notes) != 1:
                messenger.log_problem(
                    ProblemLevel.WARN,
                    f"Found {len(sermon_notes)} attachments that look like sermon notes.",
                )
            for sn in sermon_notes:
                p = assets_by_service_dir.joinpath(sn.filename)
                downloads[sn] = Download(p, is_required=False, deduplicate=False)
        else:
            for sn in sermon_notes:
                downloads[sn] = DownloadSkipped(reason="sermon notes")

        kids_videos = attachments_by_category[AssetCategory.KIDS_VIDEO]
        # Give this warning in every case because it might mean videos that
        # should be downloaded (e.g., opener, bumper) are being misclassified
        if len(kids_videos) > 1:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Found {len(kids_videos)} attachments that look like the Kids Connection video.",
            )
        if download_kids_video:
            if len(kids_videos) == 0:
                raise ValueError(
                    "Found 0 attachments that look like the Kids Connection video."
                )
            for v in kids_videos:
                _check_kids_video_week_num(v, today, messenger)
                p = assets_by_service_dir.joinpath(v.filename)
                downloads[v] = Download(p, is_required=True, deduplicate=False)
        else:
            for v in kids_videos:
                downloads[v] = DownloadSkipped(reason="kids video")

        announcements = attachments_by_category[AssetCategory.ANNOUNCEMENTS]
        if len(announcements) == 0 and require_announcements:
            raise ValueError(
                f"Found 0 attachments that look like the announcements video."
            )
        elif len(announcements) != 1:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Found {len(announcements)} attachments that look like the announcements video.",
            )
        for a in announcements:
            # Make it clear in the name which date the announcements are for,
            # to avoid confusion with the previous week's video
            stem = Path(a.filename).stem
            ext = Path(a.filename).suffix
            fname = f"{stem} {today.strftime('%Y-%m-%d')}{ext}"
            p = assets_by_service_dir.joinpath(fname)
            downloads[a] = Download(
                p, is_required=require_announcements, deduplicate=False
            )

        for img in attachments_by_category[AssetCategory.IMAGE]:
            p = _find_available_path(
                dest_dir=self._config.images_dir, name=img.filename
            )
            downloads[img] = Download(p, is_required=False, deduplicate=True)

        for vid in attachments_by_category[AssetCategory.VIDEO]:
            p = self._config.videos_dir.joinpath(vid.filename)
            # Assume the existing video is already correct
            if p.exists():
                downloads[vid] = DownloadSkipped(
                    reason=f"{p.resolve().as_posix()} already exists"
                )
            else:
                downloads[vid] = Download(p, is_required=False, deduplicate=True)

        for a in attachments:
            if a not in downloads:
                downloads[a] = DownloadSkipped(reason="unknown attachment")

        return downloads


def _find_available_path(dest_dir: Path, name: str) -> Path:
    MAX_ATTEMPTS = 1000
    file = Path(name)
    suffix = file.suffix
    stem = file.stem
    for i in range(MAX_ATTEMPTS + 1):
        new_filepath = (
            dest_dir.joinpath(f"{stem}{suffix}")
            if i == 0
            else dest_dir.joinpath(f"{stem}-{i}{suffix}")
        )
        if not new_filepath.exists():
            return new_filepath
    raise ValueError(
        f"Failed to move {name} into {dest_dir.as_posix()} because no suitable name could be found (all attempted ones were already taken)."
    )


def _find_original(p: Path) -> Optional[Path]:
    directory = p.parent
    for other in directory.iterdir():
        # TODO: This is buggy; need to check that other != p
        if p.resolve() == other.resolve() or not other.is_file():
            continue
        if filecmp.cmp(p, other):
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
