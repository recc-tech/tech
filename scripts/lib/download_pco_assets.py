import asyncio
import re
import shutil
import typing
from datetime import date, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from autochecklist import Messenger, ProblemLevel, TaskStatus
from external_services import Attachment, FileType, PlanningCenterClient

# TODO: Move these to config file
_KIDS_VIDEO_FILENAME_REGEX = re.compile(r"kids", flags=re.IGNORECASE)
_SERMON_NOTES_REGEX = re.compile(r"^notes.*", flags=re.IGNORECASE)


def locate_kids_video(dir: Path) -> Optional[Path]:
    def is_kids_video(p: Path) -> bool:
        return (
            p.is_file()
            and p.suffix.lower() in {".mp4", ".mov"}
            and bool(_KIDS_VIDEO_FILENAME_REGEX.search(p.stem))
        )

    candidates = [p for p in dir.glob("*") if is_kids_video(p)]
    if len(candidates) == 1:
        return candidates[0]
    else:
        return None


# TODO: Split this into separate functions for FOH and MCR?
def download_pco_assets(
    client: PlanningCenterClient,
    messenger: Messenger,
    today: date,
    assets_by_service_dir: Path,
    temp_assets_dir: Path,
    assets_by_type_videos_dir: Path,
    assets_by_type_images_dir: Path,
    download_kids_video: bool,
    download_notes_docx: bool,
    dry_run: bool,
) -> Optional[Path]:
    cancellation_token = messenger.allow_cancel()

    (downloads, kids_video_path) = _plan_downloads(
        client=client,
        messenger=messenger,
        today=today,
        assets_by_service_dir=assets_by_service_dir,
        temp_assets_dir=temp_assets_dir,
        assets_by_type_videos_dir=assets_by_type_videos_dir,
        download_kids_video=download_kids_video,
        download_notes_docx=download_notes_docx,
    )

    if len(downloads) == 0:
        messenger.log_problem(ProblemLevel.WARN, "No assets found to download.")
        return
    if dry_run:
        messenger.log_debug("Skipping downloading assets: dry run.")
        return None

    assets_by_service_dir.mkdir(exist_ok=True, parents=True)
    # Just in case
    assets_by_type_videos_dir.mkdir(exist_ok=True, parents=True)
    assets_by_type_images_dir.mkdir(exist_ok=True, parents=True)
    temp_assets_dir.mkdir(exist_ok=True, parents=True)

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
        if results.get(p, None) is None and p.is_relative_to(temp_assets_dir)
    ]

    messenger.log_status(
        TaskStatus.RUNNING, "Moving new images into the assets folder."
    )
    results = _merge_files(successful_image_downloads, assets_by_type_images_dir)
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


def _plan_downloads(
    client: PlanningCenterClient,
    messenger: Messenger,
    today: date,
    assets_by_service_dir: Path,
    temp_assets_dir: Path,
    assets_by_type_videos_dir: Path,
    download_kids_video: bool,
    download_notes_docx: bool,
) -> Tuple[Dict[Path, Attachment], Optional[Path]]:
    messenger.log_status(
        TaskStatus.RUNNING, "Looking for attachments in Planning Center."
    )
    plan = client.find_plan_by_date(today)
    attachments = client.find_attachments(plan.id)
    (
        kids_videos,
        sermon_notes,
        other_images,
        other_videos,
        unknown_attachments,
    ) = _classify_attachments(attachments, messenger)
    if len(sermon_notes) != 1 and download_notes_docx:
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Found {len(sermon_notes)} attachments that look like sermon notes.",
        )
    if len(kids_videos) != 1 and download_kids_video:
        raise ValueError(
            f"Found {len(kids_videos)} attachments that look like the Kids Connection video."
        )
    kids_video = _any(kids_videos) if len(kids_videos) > 0 else None
    messenger.log_debug(
        f"{len(attachments)} attachments found on PCO.\n- Kids video: {kids_video}\n- Sermon notes: {sermon_notes}\n- Other images: {other_images}\n- Other videos: {other_videos}\n- Unknown: {unknown_attachments}"
    )

    messenger.log_status(TaskStatus.RUNNING, "Preparing for download.")
    downloads: Dict[Path, Attachment] = {}
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
        downloads[temp_assets_dir.joinpath(img.filename)] = img
    for vid in other_videos:
        vid_path = assets_by_type_videos_dir.joinpath(vid.filename)
        # Assume the existing video is already correct
        if not vid_path.exists():
            downloads[vid_path] = vid

    return (downloads, kids_video_path)


def _classify_attachments(
    attachments: Set[Attachment], messenger: Messenger
) -> Tuple[
    Set[Attachment], Set[Attachment], Set[Attachment], Set[Attachment], Set[Attachment]
]:
    def is_kids_video(a: Attachment) -> bool:
        return a.file_type == FileType.VIDEO and bool(
            _KIDS_VIDEO_FILENAME_REGEX.search(a.filename)
        )

    def is_sermon_notes(a: Attachment) -> bool:
        return a.file_type == FileType.DOCX and bool(
            _SERMON_NOTES_REGEX.fullmatch(a.filename)
        )

    # Don't mutate the input
    attachments = set(attachments)
    kids_videos = {a for a in attachments if is_kids_video(a)}
    attachments -= kids_videos
    notes = {a for a in attachments if is_sermon_notes(a)}
    attachments -= notes
    other_images = {a for a in attachments if a.file_type == FileType.IMAGE}
    attachments -= other_images
    other_videos = {a for a in attachments if a.file_type == FileType.VIDEO}
    attachments -= other_videos

    return kids_videos, notes, other_images, other_videos, attachments


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
