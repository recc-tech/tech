import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

from autochecklist import LogLevel, Messenger
from vimeo import VimeoClient  # type: ignore

NEW_VIDEO_TIMEDELTA = timedelta(hours=3)
"""
Maximum time elapsed since today's video was uploaded.
"""

RETRY_SECONDS = 60
"""
Number of seconds to wait between checks for the new video on Vimeo.
"""

CAPTIONS_TYPE = "subtitles"

CAPTIONS_LANGUAGE = "en-CA"

CAPTIONS_NAME = "English (Canada)"


def get_video_data(
    messenger: Messenger, client: VimeoClient, task_name: str
) -> Tuple[str, str]:
    # Wait for the video to be posted
    while True:
        response = client.get(  # type: ignore
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
            > NEW_VIDEO_TIMEDELTA
        ):
            messenger.log(
                task_name,
                LogLevel.INFO,
                f"Video not yet found on Vimeo. Retrying in {RETRY_SECONDS} seconds.",
            )
            time.sleep(RETRY_SECONDS)
        else:
            messenger.log(
                task_name,
                LogLevel.INFO,
                f"Found newly-uploaded Vimeo video at URI '{response_data['uri']}'.",
            )
            break

    video_uri = response_data["uri"]
    texttrack_uri = response_data["metadata"]["connections"]["texttracks"]["uri"]
    return (video_uri, texttrack_uri)


def rename_video(video_uri: str, new_title: str, client: VimeoClient):
    response = client.patch(  # type: ignore
        video_uri,
        data={"name": new_title},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Vimeo client failed to rename video (HTTP status {response.status_code})."
        )


def upload_captions_to_vimeo(
    final_captions_file: Path,
    texttrack_uri: str,
    messenger: Messenger,
    client: VimeoClient,
    task_name: str,
):
    # See https://developer.vimeo.com/api/upload/texttracks

    # (1) Get text track URI: done in get_vimeo_video_data()

    # (2) Get upload link for text track
    (upload_link, uri) = _get_vimeo_texttrack_upload_link(texttrack_uri, client)
    messenger.log(
        task_name,
        LogLevel.INFO,
        f"Got text track upload link and URI for Vimeo video: upload link '{upload_link}', URI '{uri}'.",
    )

    # (3) Upload text track
    _upload_texttrack(final_captions_file, upload_link, client)
    messenger.log(task_name, LogLevel.INFO, "Uploaded text track for Vimeo video.")

    # (4) Mark text track as active
    _activate_texttrack(uri, client)
    messenger.log(
        task_name,
        LogLevel.INFO,
        "Marked newly-uploaded text track for Vimeo video as active.",
    )


def _get_vimeo_texttrack_upload_link(
    texttrack_uri: str, client: VimeoClient
) -> Tuple[str, str]:
    response = client.post(  # type: ignore
        texttrack_uri,
        data={
            "type": CAPTIONS_TYPE,
            "language": CAPTIONS_LANGUAGE,
            "name": CAPTIONS_NAME,
        },
    )

    status_code = response.status_code  # type: ignore
    if status_code != 201:
        raise RuntimeError(
            f"Failed to get text track upload link for Vimeo video (HTTP status {status_code})."
        )

    response_body = response.json()  # type: ignore
    return (response_body["link"], response_body["uri"])


def _upload_texttrack(
    final_captions_file: Path,
    upload_link: str,
    client: VimeoClient,
):
    # Read the captions from final.vtt
    # If you don't set the encoding to UTF-8, then Unicode characters get mangled
    with open(final_captions_file, "r", encoding="utf-8") as f:
        vtt = f.read()

    # If you don't encode the VTT file as UTF-8, then for some reason some characters get dropped at the end of the
    # file (if there are Unicode characters)
    response = client.put(upload_link, data=vtt.encode("utf-8"))  # type: ignore

    status_code = response.status_code
    if status_code != 200:
        raise RuntimeError(
            f"Failed to upload text track for Vimeo video (HTTP status {status_code})"
        )


def _activate_texttrack(texttrack_uri: str, client: VimeoClient):
    response = client.patch(texttrack_uri, data={"active": True})  # type: ignore

    status_code = response.status_code
    if status_code != 200:
        raise RuntimeError(
            f"Failed to mark text track at link '{texttrack_uri}' as active (HTTP status {status_code})."
        )
