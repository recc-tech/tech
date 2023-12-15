import asyncio
import filecmp
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Set, Tuple

from autochecklist import Messenger, ProblemLevel, TaskStatus
from common import Attachment, PlanningCenterClient
from mcr_setup.config import McrSetupConfig
from slides import SlideBlueprintReader, SlideGenerator


def download_message_notes(client: PlanningCenterClient, config: McrSetupConfig):
    today = config.now.date()
    plan = client.find_plan_by_date(today)
    message_notes = client.find_message_notes(plan.id)
    config.message_notes_file.parent.mkdir(exist_ok=True, parents=True)
    with open(config.message_notes_file, "w", encoding="utf-8") as f:
        f.write(message_notes)


def generate_backup_slides(
    reader: SlideBlueprintReader,
    generator: SlideGenerator,
    config: McrSetupConfig,
    messenger: Messenger,
):
    messenger.log_status(
        TaskStatus.RUNNING,
        f"Reading input from {config.message_notes_file.as_posix()}.",
    )
    blueprints = reader.load_message_notes(config.message_notes_file)

    messenger.log_status(
        TaskStatus.RUNNING,
        f"Saving slide blueprints to {config.backup_slides_json_file}.",
    )
    reader.save_json(config.backup_slides_json_file, blueprints)

    messenger.log_status(TaskStatus.RUNNING, f"Generating images.")
    blueprints_with_prefix = [
        b.with_name(f"LTD{i} - {b.name}" if b.name else f"LTD{i}")
        for i, b in enumerate(blueprints, start=1)
    ]
    slides = generator.generate_lower_third_slide(
        blueprints_with_prefix, show_backdrop=True
    )

    messenger.log_status(TaskStatus.RUNNING, f"Saving images.")
    for s in slides:
        s.save(config.assets_by_service_dir)


def download_assets(
    client: PlanningCenterClient, config: McrSetupConfig, messenger: Messenger
):
    cancellation_token = messenger.allow_cancel()

    today = config.now.date()
    plan = client.find_plan_by_date(today)
    attachments = client.find_attachments(plan.id)

    kids_video, sermon_notes, other_images, other_videos = _classify_attachments(
        attachments
    )

    config.assets_by_service_dir.mkdir(exist_ok=True, parents=True)

    # Prepare for downloads
    messenger.log_status(TaskStatus.RUNNING, "Preparing for download.")
    downloads: List[Tuple[Attachment, Path]] = []
    archived_files: List[Tuple[Path, Path]] = []
    if len(kids_video) != 1:
        raise ValueError(
            f"Found {len(kids_video)} attachments that look like the Kids Connection video."
        )
    kids_video = _any(kids_video)
    kids_video_path = config.assets_by_service_dir.joinpath(kids_video.filename)
    downloads.append((kids_video, kids_video_path))
    if len(sermon_notes) == 0:
        messenger.log_problem(
            ProblemLevel.WARN, "Found 0 attachments that look like the sermon notes."
        )
    elif len(sermon_notes) == 1:
        sermon_notes = _any(sermon_notes)
        sermon_notes_path = config.assets_by_service_dir.joinpath(sermon_notes.filename)
        downloads.append((sermon_notes, sermon_notes_path))
    else:
        raise ValueError(
            f"Found {len(sermon_notes)} attachments that look like sermon notes."
        )
    for img in other_images:
        img_path = config.assets_by_type_images_dir.joinpath(img.filename)
        if img_path.exists():
            timestamp = (
                f"{today.strftime('%Y-%m-%d')} {datetime.now().strftime('%H-%M-%S-%f')}"
            )
            # Microseconds --> milliseconds
            timestamp = timestamp[:-3]
            archived_img_name = (
                f"{img_path.stem} (archived {timestamp}){img_path.suffix}"
            )
            archived_img_path = config.assets_by_type_archive_dir.joinpath(
                archived_img_name
            )
            archived_files.append((img_path, archived_img_path))
            # Copy instead of moving in case an error occurs before the new
            # file is downloaded
            shutil.copyfile(img_path, archived_img_path)
        downloads.append((img, img_path))
    for vid in other_videos:
        vid_path = config.assets_by_type_videos_dir.joinpath(vid.filename)
        # Assume the existing video is already correct
        if not vid_path.exists():
            downloads.append((vid, vid_path))

    messenger.log_status(TaskStatus.RUNNING, "Downloading new assets.")
    try:
        asyncio.run(client.download_attachments(downloads, cancellation_token))
    except BaseException:
        # The Planning Center client should take care of deleting
        # partially-downloaded assets on error.
        # Don't bother deleting assets that were successfully downloaded: the
        # user can easily take care of those if needed.
        for live_path, archived_path in archived_files:
            shutil.move(archived_path, live_path)
            archived_path.unlink(missing_ok=True)
        raise

    # If new and existing files were the same, no need to keep archived copy
    if len(archived_files) > 0:
        messenger.log_status(
            TaskStatus.RUNNING, "Comparing new assets with existing ones."
        )
    for live_path, archived_path in archived_files:
        same = filecmp.cmp(live_path, archived_path, shallow=False)
        if same:
            archived_path.unlink()


_VIDEO_CONTENT_TYPES = {
    "application/mp4",
    "application/mxf",
    "video/av1",
    "video/avi",
    "video/h264",
    "video/h264-rcdo",
    "video/h264-svc",
    "video/mp4",
    "video/mp4v-es",
    "video/mpeg",
    "video/quicktime",
    "video/x-ms-asf",
    "video/x-ms-wmv",
}
_KIDS_VIDEO_FILENAME_REGEX = re.compile(r"^kids.*", flags=re.IGNORECASE)
_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_SERMON_NOTES_REGEX = re.compile(r"^notes\s*-.*", flags=re.IGNORECASE)
_IMAGE_CONTENT_TYPES = {"image/bmp", "image/jpeg", "image/png", "image/tiff"}


def _classify_attachments(
    attachments: Set[Attachment],
) -> Tuple[Set[Attachment], Set[Attachment], Set[Attachment], Set[Attachment]]:
    kids_videos = {
        a
        for a in attachments
        if a.content_type.lower() in _VIDEO_CONTENT_TYPES
        and _KIDS_VIDEO_FILENAME_REGEX.fullmatch(a.filename)
    }
    attachments -= kids_videos
    notes = {
        a
        for a in attachments
        if a.content_type.lower() == _DOCX_CONTENT_TYPE
        and _SERMON_NOTES_REGEX.fullmatch(a.filename)
    }
    attachments -= notes
    other_images = {
        a for a in attachments if a.content_type.lower() in _IMAGE_CONTENT_TYPES
    }
    attachments -= other_images
    other_videos = {
        a for a in attachments if a.content_type.lower() in _VIDEO_CONTENT_TYPES
    }
    return kids_videos, notes, other_images, other_videos


def _any(s: Set[Attachment]) -> Attachment:
    for x in s:
        return x
    raise ValueError("Empty sequence.")
