import asyncio
import filecmp
import re
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

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

    messenger.log_status(
        TaskStatus.DONE,
        f"Generated {len(slides)} slides in {config.assets_by_service_dir.as_posix()}.",
    )


def download_assets(
    client: PlanningCenterClient, config: McrSetupConfig, messenger: Messenger
):
    cancellation_token = messenger.allow_cancel()

    today = config.now.date()
    plan = client.find_plan_by_date(today)
    attachments = client.find_attachments(plan.id)

    (
        kids_video,
        sermon_notes,
        other_images,
        other_videos,
        unknown_attachments,
    ) = _classify_attachments(attachments)
    messenger.log_debug(
        f"{len(attachments)} attachments found on PCO.\n- Kids video: {kids_video}\n- Sermon notes: {sermon_notes}\n- Other images: {other_images}\n- Other videos: {other_videos}\n- Unknown: {unknown_attachments}"
    )

    config.assets_by_service_dir.mkdir(exist_ok=True, parents=True)

    # Prepare for downloads
    # IMPORTANT: the kids video must be the first thing in the downloads list
    messenger.log_status(TaskStatus.RUNNING, "Preparing for download.")
    downloads: List[Tuple[Attachment, Path, Optional[Path]]] = []
    if len(kids_video) != 1:
        raise ValueError(
            f"Found {len(kids_video)} attachments that look like the Kids Connection video."
        )
    kids_video = _any(kids_video)
    kids_video_path = config.assets_by_service_dir.joinpath(kids_video.filename)
    downloads.append((kids_video, kids_video_path, None))
    if len(sermon_notes) != 1:
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Found {len(sermon_notes)} attachments that look like sermon notes.",
        )
    for sn in sermon_notes:
        sermon_notes_path = config.assets_by_service_dir.joinpath(sn.filename)
        downloads.append((sn, sermon_notes_path, None))
    for img in other_images:
        img_path = config.assets_by_type_images_dir.joinpath(img.filename)
        if img_path.exists():
            timestamp = (
                f"{today.strftime('%Y-%m-%d')} {datetime.now().strftime('%H-%M-%S-%f')}"
            )
            # Microseconds --> milliseconds
            timestamp = timestamp[:-3]
            name = f"{img_path.stem} (archived {timestamp}){img_path.suffix}"
            archived_img_path = config.assets_by_type_archive_dir.joinpath(name)
            # Copy instead of moving in case an error occurs before the new
            # file is downloaded
            shutil.copyfile(img_path, archived_img_path)
        else:
            archived_img_path = None
        downloads.append((img, img_path, archived_img_path))
    for vid in other_videos:
        vid_path = config.assets_by_type_videos_dir.joinpath(vid.filename)
        # Assume the existing video is already correct
        if not vid_path.exists():
            downloads.append((vid, vid_path, None))

    messenger.log_status(TaskStatus.RUNNING, "Downloading new assets.")
    results = asyncio.run(
        client.download_attachments(
            downloads=[(a, p) for (a, p, _) in downloads],
            messenger=messenger,
            cancellation_token=cancellation_token,
        )
    )

    messenger.log_status(TaskStatus.RUNNING, "Checking downloaded assets.")
    for i, (_, live_path, archive_path) in enumerate(downloads):
        if i == 0:
            # Deal with the kids video last so an exception can be thrown
            continue
        if i >= len(results):
            break
        try:
            if results[i] is not None:
                messenger.log_problem(
                    ProblemLevel.WARN,
                    f"Download to '{live_path.as_posix()}' failed: {results[i]} ({type(results[i]).__name__}).",
                )
            if results[i] is not None and archive_path is not None:
                # Restore from archive
                shutil.move(src=archive_path, dst=live_path)
            elif results[i] is None and archive_path is not None:
                same = filecmp.cmp(live_path, archive_path, shallow=False)
                if same:
                    # No need to keep archived copy
                    archive_path.unlink(missing_ok=True)
        except BaseException as e:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Failed to check download '{live_path.as_posix()}': {e}",
                traceback.format_exc(),
            )

    if results[0] is not None:
        raise Exception(
            f"Failed to download the Kids Connection video: {results[0]} ({type(results[0]).__name__})."
        ) from results[0]


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
_SERMON_NOTES_REGEX = re.compile(r"^notes.*", flags=re.IGNORECASE)
_IMAGE_CONTENT_TYPES = {"image/bmp", "image/jpeg", "image/png", "image/tiff"}


def _classify_attachments(
    attachments: Set[Attachment],
) -> Tuple[
    Set[Attachment], Set[Attachment], Set[Attachment], Set[Attachment], Set[Attachment]
]:
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
    attachments -= other_videos
    return kids_videos, notes, other_images, other_videos, attachments


def _any(s: Set[Attachment]) -> Attachment:
    for x in s:
        return x
    raise ValueError("Empty sequence.")
