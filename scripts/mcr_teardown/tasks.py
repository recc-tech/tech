import logging
import shutil
import stat
from datetime import datetime
from pathlib import Path

import mcr_teardown.rebroadcasts as rebroadcasts
import mcr_teardown.vimeo as recc_vimeo
from boxcast_client import BoxCastClientFactory
from config import Config
from messenger import Messenger
from vimeo import VimeoClient  # type: ignore


def create_rebroadcast_1pm(
    boxcast_client_factory: BoxCastClientFactory, config: Config, messenger: Messenger
):
    source_broadcast_id = config.boxcast_event_id
    start_datetime = datetime.now().replace(hour=13, minute=0, second=0)
    client = boxcast_client_factory.get_client()
    rebroadcasts.create_rebroadcast(
        source_broadcast_id, start_datetime, client, messenger
    )


def create_rebroadcast_5pm(
    boxcast_client_factory: BoxCastClientFactory, config: Config, messenger: Messenger
):
    source_broadcast_id = config.boxcast_event_id
    start_datetime = datetime.now().replace(hour=17, minute=0, second=0)
    client = boxcast_client_factory.get_client()
    rebroadcasts.create_rebroadcast(
        source_broadcast_id, start_datetime, client, messenger
    )


def create_rebroadcast_7pm(
    boxcast_client_factory: BoxCastClientFactory, config: Config, messenger: Messenger
):
    source_broadcast_id = config.boxcast_event_id
    start_datetime = datetime.now().replace(hour=19, minute=0, second=0)
    client = boxcast_client_factory.get_client()
    rebroadcasts.create_rebroadcast(
        source_broadcast_id, start_datetime, client, messenger
    )


def get_vimeo_video_data(
    messenger: Messenger, vimeo_client: VimeoClient, config: Config
):
    (video_uri, texttrack_uri) = recc_vimeo.get_video_data(messenger, vimeo_client)

    config.vimeo_video_uri = video_uri
    config.vimeo_video_texttracks_uri = texttrack_uri


def rename_video_on_vimeo(config: Config, vimeo_client: VimeoClient):
    video_uri = config.vimeo_video_uri
    if video_uri is None:
        raise ValueError(
            "The link to the Vimeo video is unknown (config.vimeo_video_uri was not set)."
        )

    date_ymd = datetime.now().strftime("%Y-%m-%d")
    new_title = f"{date_ymd} | {config.message_series} | {config.message_title}"

    recc_vimeo.rename_video(video_uri, new_title, vimeo_client)


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
    final_captions_file = config.captions_dir.joinpath("final.vtt")
    texttrack_uri = config.vimeo_video_texttracks_uri
    if texttrack_uri is None:
        raise ValueError(
            "The link to the Vimeo text track is unknown (config.vimeo_video_texttracks_uri was not set)."
        )

    recc_vimeo.upload_captions_to_vimeo(
        final_captions_file, texttrack_uri, messenger, vimeo_client
    )


def _mark_read_only_and_copy(source: Path, destination: Path, messenger: Messenger):
    if not source.exists():
        raise ValueError(f"File '{source}' does not exist.")

    if destination.exists():
        messenger.log(
            logging.WARN,
            f"File '{destination}' already exists and will be overwritten.",
        )

    # Copy the file
    shutil.copy(src=source, dst=destination)
    messenger.log(logging.DEBUG, f"Copied '{source}' to '{destination}'.")

    # Mark the original file as read-only
    source.chmod(stat.S_IREAD)
    messenger.log(logging.DEBUG, f"Marked '{source}' as read-only.")
