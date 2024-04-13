import asyncio
import re
import shutil
import typing
from datetime import date, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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

    # TODO: Split this into separate functions for FOH and MCR?
    def download_pco_assets(
        self,
        client: PlanningCenterClient,
        messenger: Messenger,
        download_kids_video: bool,
        download_notes_docx: bool,
        dry_run: bool,
    ) -> Optional[Path]:
        cancellation_token = messenger.allow_cancel()

        (downloads, kids_video_path) = self._plan_downloads(
            client=client,
            messenger=messenger,
            download_kids_video=download_kids_video,
            download_notes_docx=download_notes_docx,
        )

        if len(downloads) == 0:
            messenger.log_problem(ProblemLevel.WARN, "No assets found to download.")
            return
        if dry_run:
            messenger.log_debug("Skipping downloading assets: dry run.")
            return None

        self._config.assets_by_service_dir.mkdir(exist_ok=True, parents=True)
        # Just in case
        self._config.videos_dir.mkdir(exist_ok=True, parents=True)
        self._config.images_dir.mkdir(exist_ok=True, parents=True)
        self._config.temp_assets_dir.mkdir(exist_ok=True, parents=True)

        messenger.log_status(TaskStatus.RUNNING, "Downloading new assets.")
        results = asyncio.run(
            client.download_attachments(downloads, messenger, cancellation_token)
        )
        if download_kids_video:
            if kids_video_path is None:
                raise ValueError("Internal error: the kids video path is not known.")
            kids_video_result = results[kids_video_path]
            if kids_video_result is not None:
                raise Exception(
                    f"Failed to download the Kids Connection video: {kids_video_result} ({type(kids_video_result).__name__})."
                ) from kids_video_result
        for path in downloads.keys():
            if path not in results:
                messenger.log_problem(
                    ProblemLevel.WARN,
                    f"The result of the download to '{path.as_posix()}' is unknown.",
                )
            elif results[path] is not None:
                # TODO: Refactor log_problem to take exception object as input
                messenger.log_problem(
                    ProblemLevel.WARN,
                    f"Download to '{path.as_posix()}' failed: {results[path]} ({type(results[path]).__name__}).",
                )
        successful_image_downloads = [
            p
            for p in downloads.keys()
            if results.get(p, None) is None
            and p.is_relative_to(self._config.temp_assets_dir)
        ]

        messenger.log_status(
            TaskStatus.RUNNING, "Moving new images into the assets folder."
        )
        results = _merge_files(successful_image_downloads, self._config.images_dir)
        for p, r in zip(successful_image_downloads, results):
            match r:
                case MergeFileResult.SUCCESS:
                    messenger.log_debug(
                        f"{p.name} was successfully moved to the assets folder."
                    )
                case MergeFileResult.ALREADY_EXISTS:
                    messenger.log_debug(
                        f"{p.name} has the same contents as an existing file, so it was not moved to the assets folder."
                    )
                case MergeFileResult.RENAME_FAILED:
                    messenger.log_problem(
                        ProblemLevel.WARN,
                        f"Failed to move {p.name} to the assets folder because no suitable name could be found (all attempted ones were already taken).",
                    )
                case MergeFileResult.RENAMED:
                    messenger.log_problem(
                        ProblemLevel.WARN,
                        f"There is already a file called {p.name} in the assets folder, but its contents are different. Maybe the old file should be archived.",
                    )

        if download_kids_video:
            return typing.cast(Path, kids_video_path)
        else:
            return None

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
    ) -> Tuple[Dict[Path, Attachment], Optional[Path]]:
        messenger.log_status(
            TaskStatus.RUNNING, "Looking for attachments in Planning Center."
        )
        today = self._config.start_time.date()
        plan = client.find_plan_by_date(today)
        attachments = client.find_attachments(plan.id)
        category_by_attachment = {a: self._classify(a) for a in attachments}
        attachments_by_category = {
            cat: {a for (a, c) in category_by_attachment.items() if c == cat}
            for cat in AssetCategory
        }
        sermon_notes = attachments_by_category[AssetCategory.SERMON_NOTES]
        if len(sermon_notes) != 1 and download_notes_docx:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Found {len(sermon_notes)} attachments that look like sermon notes.",
            )
        kids_videos = attachments_by_category[AssetCategory.KIDS_VIDEO]
        if len(kids_videos) != 1 and download_kids_video:
            raise ValueError(
                f"Found {len(kids_videos)} attachments that look like the Kids Connection video."
            )
        kids_video = _any(kids_videos) if len(kids_videos) > 0 else None
        announcements = attachments_by_category[AssetCategory.ANNOUNCEMENTS]
        if len(announcements) != 1:
            raise ValueError(
                f"Found {len(announcements)} attachments that look like the announcements video."
            )
        announcements = _any(announcements)
        other_images = attachments_by_category[AssetCategory.IMAGE]
        other_videos = attachments_by_category[AssetCategory.VIDEO]
        unknown_attachments = attachments_by_category[AssetCategory.UNKNOWN]
        messenger.log_debug(
            f"{len(attachments)} attachments found on PCO.\n"
            f" * Announcements video: {announcements}\n"
            f" * Kids video: {kids_video}\n"
            f" * Sermon notes: {sermon_notes}\n"
            f" * Other images: {other_images}\n"
            f" * Other videos: {other_videos}\n"
            f" * Unknown: {unknown_attachments}"
        )

        messenger.log_status(TaskStatus.RUNNING, "Preparing for download.")
        assets_by_service_dir = self._config.assets_by_service_dir
        downloads: Dict[Path, Attachment] = {}
        announcements_path = assets_by_service_dir.joinpath(announcements.filename)
        downloads[announcements_path] = announcements
        kids_video_path = None
        if download_kids_video:
            # Should never happen, but check to make Pyright happy
            if kids_video is None:
                raise ValueError("Missing kids video.")
            _check_kids_video_week_num(kids_video, today, messenger)
            kids_video_path = assets_by_service_dir.joinpath(kids_video.filename)
            downloads[kids_video_path] = kids_video
        if download_notes_docx:
            for sn in sermon_notes:
                downloads[assets_by_service_dir.joinpath(sn.filename)] = sn
        for img in other_images:
            downloads[self._config.temp_assets_dir.joinpath(img.filename)] = img
        for vid in other_videos:
            vid_path = self._config.videos_dir.joinpath(vid.filename)
            # Assume the existing video is already correct
            if not vid_path.exists():
                downloads[vid_path] = vid

        return (downloads, kids_video_path)


def _any(s: Set[Attachment]) -> Attachment:
    for x in s:
        return x
    raise ValueError("Empty sequence.")


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


class MergeFileResult(Enum):
    SUCCESS = auto()
    """The file was moved to the target directory."""
    ALREADY_EXISTS = auto()
    """The file matches an existing one."""
    RENAMED = auto()
    """
    The file was moved to the target directory, but its original name was
    already taken.
    """
    RENAME_FAILED = auto()
    """
    The file could not be moved to the target directory because no suitable
    name could be found that did not overwrite an existing file.
    """


def _merge_files(files: List[Path], dir: Path) -> List[MergeFileResult]:
    """
    Merge the given set of files into the given directory.
    If a file has the same contents as any of the files already in `dir`,
    delete it.
    Otherwise, move it into `dir`.
    If an existing file already has the same name, rename the new file.
    """
    existing_image_contents = {p.read_bytes() for p in dir.iterdir() if p.is_file()}
    results: List[MergeFileResult] = []
    for p in files:
        if p.read_bytes() in existing_image_contents:
            p.unlink()
            results.append(MergeFileResult.ALREADY_EXISTS)
        else:
            required_attempts = _move_without_overwriting(p, dir, max_attempts=100)
            if required_attempts < 0:
                results.append(MergeFileResult.RENAME_FAILED)
            elif required_attempts == 0:
                results.append(MergeFileResult.SUCCESS)
            else:
                results.append(MergeFileResult.RENAMED)
    return results


def _move_without_overwriting(file: Path, dest_dir: Path, max_attempts: int) -> int:
    suffix = file.suffix
    stem = file.stem
    required_attempts = -1
    for i in range(max_attempts + 1):
        new_filepath = (
            dest_dir.joinpath(f"{stem}{suffix}")
            if i == 0
            else dest_dir.joinpath(f"{stem}-{i}{suffix}")
        )
        if not new_filepath.exists():
            shutil.move(file, new_filepath)
            required_attempts = i
            break
    return required_attempts
