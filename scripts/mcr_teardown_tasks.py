import logging
import shutil
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vimeo import VimeoClient

from config import Config
from messenger import Messenger

VIMEO_NEW_VIDEO_TIMEDELTA = timedelta(hours=3)
"""
Maximum time elapsed since today's video was uploaded.
"""

VIMEO_RETRY_SECONDS = 60
"""
Number of seconds to wait between checks for the new video on Vimeo.
"""


def rename_video_on_vimeo(
    messenger: Messenger, config: Config, vimeo_client: VimeoClient
):
    # Wait for the video to be posted
    while True:
        response = vimeo_client.get(  # type: ignore
            "/me/videos",
            params={
                "fields": "uri,created_time",
                "per_page": 1,
                "sort": "date",
                "direction": "desc",
            },
        )

        if response.status_code != 200:  # type: ignore
            raise RuntimeError(
                f"Vimeo client failed to access GET /videos (HTTP status {response.status_code})."
            )

        response_body = response.json()  # type: ignore
        response_data = response.json()["data"][0]  # type: ignore
        if response_body["total"] < 1 or (
            # TODO: double-check that we have the right video by also looking at the name or something?
            datetime.now(timezone.utc)
            - datetime.fromisoformat(response_data["created_time"])
            > VIMEO_NEW_VIDEO_TIMEDELTA
        ):
            messenger.log(
                logging.DEBUG,
                f"Video not yet found on Vimeo. Retrying in {VIMEO_RETRY_SECONDS} seconds.",
            )
            time.sleep(VIMEO_RETRY_SECONDS)
        else:
            uri = response_data["uri"]
            messenger.log(
                logging.DEBUG, f"Found newly-uploaded Vimeo video at URI '{uri}'."
            )
            break

    # Rename the video
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    response = vimeo_client.patch(  # type: ignore
        uri,
        data={"name": f"{date_ymd} | {config.message_series} | {config.message_title}"},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Vimeo client failed to rename video (HTTP status {response.status_code})."
        )


def copy_captions_original_to_without_worship(messenger: Messenger, config: Config):
    _mark_read_only_and_copy(
        config.captions_dir.joinpath("original.vtt"),
        config.captions_dir.joinpath("without_worship.vtt"),
        messenger,
    )


def copy_captions_without_worship_to_final(messenger: Messenger, config: Config):
    _mark_read_only_and_copy(
        config.captions_dir.joinpath("original.vtt"),
        config.captions_dir.joinpath("without_worship.vtt"),
        messenger,
    )


def _mark_read_only_and_copy(source: Path, destination: Path, messenger: Messenger):
    if not source.exists():
        raise ValueError(f"File '{source}' does not exist.")

    # Mark the original file as read-only
    source.chmod(stat.S_IREAD)
    messenger.log(logging.DEBUG, f"Marked '{source}' as read-only.")

    if destination.exists():
        messenger.log(
            logging.WARN,
            f"File '{destination}' already exists and will be overwritten.",
        )

    # Copy the file
    shutil.copy(src=source, dst=destination)
    messenger.log(logging.DEBUG, f"Copied '{source}' to '{destination}'.")
