import logging
import shutil
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

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

VIMEO_CAPTIONS_TYPE = "subtitles"

VIMEO_CAPTIONS_LANGUAGE = "en-CA"

VIMEO_CAPTIONS_NAME = "English (Canada)"


def get_vimeo_video_data(
    messenger: Messenger, vimeo_client: VimeoClient, config: Config
):
    # Wait for the video to be posted
    while True:
        response = vimeo_client.get(  # type: ignore
            "/me/videos",
            params={
                "fields": "created_time,uri,metadata.connections.texttracks.uri",
                "per_page": 1,
                "sort": "date",
                "direction": "desc",
            },
        )

        status_code: int = response.status_code  # type: ignore
        if status_code != 200:
            raise RuntimeError(
                f"Vimeo client failed to access GET /videos (HTTP status {status_code})."
            )

        response_body = response.json()  # type: ignore
        response_data = response.json()["data"][0]  # type: ignore
        if response_body["total"] < 1 or (
            # TODO: double-check that we have the right video by also looking at the name or something?
            datetime.now(timezone.utc)
            - datetime.fromisoformat(response_data["created_time"])  # type: ignore
            > VIMEO_NEW_VIDEO_TIMEDELTA
        ):
            messenger.log(
                logging.DEBUG,
                f"Video not yet found on Vimeo. Retrying in {VIMEO_RETRY_SECONDS} seconds.",
            )
            time.sleep(VIMEO_RETRY_SECONDS)
        else:
            messenger.log(
                logging.DEBUG,
                f"Found newly-uploaded Vimeo video at URI '{response_data['uri']}'.",
            )
            break

    # Save data for use by later steps
    config.vimeo_video_uri = response_data["uri"]
    config.vimeo_video_texttracks_uri = response_data["metadata"]["connections"][
        "texttracks"
    ]["uri"]


def rename_video_on_vimeo(config: Config, vimeo_client: VimeoClient):
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    response = vimeo_client.patch(  # type: ignore
        config.vimeo_video_uri,
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
        config.captions_dir.joinpath("without_worship.vtt"),
        config.captions_dir.joinpath("final.vtt"),
        messenger,
    )


def upload_captions_to_vimeo(
    config: Config, messenger: Messenger, vimeo_client: VimeoClient
):
    # See https://developer.vimeo.com/api/upload/texttracks

    # (1) Get text track URI: done in get_vimeo_video_data()

    # (2) Get upload link for text track
    (upload_link, uri) = _get_vimeo_texttrack_upload_link(config, vimeo_client)
    messenger.log(
        logging.DEBUG,
        f"Got text track upload link and URI for Vimeo video: upload link '{upload_link}', URI '{uri}'.",
    )

    # (3) Upload text track
    _upload_texttrack(upload_link, config, vimeo_client)
    messenger.log(logging.DEBUG, "Uploaded text track for Vimeo video.")

    # (4) Mark text track as active
    _activate_texttrack(uri, vimeo_client)
    messenger.log(
        logging.DEBUG, "Marked newly-uploaded text track for Vimeo video as active."
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


def _get_vimeo_texttrack_upload_link(
    config: Config, vimeo_client: VimeoClient
) -> Tuple[str, str]:
    response = vimeo_client.post(  # type: ignore
        config.vimeo_video_texttracks_uri,
        data={
            "type": VIMEO_CAPTIONS_TYPE,
            "language": VIMEO_CAPTIONS_LANGUAGE,
            "name": VIMEO_CAPTIONS_NAME,
        },
    )

    status_code = response.status_code  # type: ignore
    if status_code != 201:
        raise RuntimeError(
            f"Failed to get text track upload link for Vimeo video (HTTP status {status_code})."
        )

    response_body = response.json()  # type: ignore
    return (response_body["link"], response_body["uri"])


def _upload_texttrack(upload_link: str, config: Config, vimeo_client: VimeoClient):
    # Read the captions from final.vtt
    # If you don't set the encoding to UTF-8, then Unicode characters get mangled
    with open(config.captions_dir.joinpath("final.vtt"), "r", encoding="utf-8") as f:
        vtt = f.read()

    # If you don't encode the VTT file as UTF-8, then for some reason some characters get dropped at the end of the
    # file (if there are Unicode characters)
    response = vimeo_client.put(upload_link, data=vtt.encode("utf-8"))  # type: ignore

    status_code = response.status_code
    if status_code != 200:
        raise RuntimeError(
            f"Failed to upload text track for Vimeo video (HTTP status {status_code})"
        )


def _activate_texttrack(texttrack_uri: str, vimeo_client: VimeoClient):
    response = vimeo_client.patch(texttrack_uri, data={"active": True})  # type: ignore

    status_code = response.status_code
    if status_code != 200:
        raise RuntimeError(
            f"Failed to mark text track at link '{texttrack_uri}' as active (HTTP status {status_code})."
        )
