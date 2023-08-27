import shutil
import stat
from datetime import datetime

import mcr_teardown.boxcast as boxcast_tasks
import mcr_teardown.vimeo as vimeo_tasks
from autochecklist import Messenger, ProblemLevel
from mcr_teardown.boxcast import BoxCastClientFactory
from mcr_teardown.config import McrTeardownConfig
from mcr_teardown.vimeo import ReccVimeoClient


def create_rebroadcast_1pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    with boxcast_client_factory.get_client() as client:
        boxcast_tasks.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=datetime.now().replace(hour=13, minute=0, second=0),
            client=client,
            messenger=messenger,
        )


def create_rebroadcast_5pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    with boxcast_client_factory.get_client() as client:
        boxcast_tasks.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=datetime.now().replace(hour=17, minute=0, second=0),
            client=client,
            messenger=messenger,
        )


def create_rebroadcast_7pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    with boxcast_client_factory.get_client() as client:
        boxcast_tasks.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=datetime.now().replace(hour=19, minute=0, second=0),
            client=client,
            messenger=messenger,
        )


def export_to_vimeo(
    boxcast_client_factory: BoxCastClientFactory, config: McrTeardownConfig
):
    with boxcast_client_factory.get_client() as client:
        boxcast_tasks.export_to_vimeo(client=client, event_url=config.live_event_url)


def get_vimeo_video_data(
    messenger: Messenger,
    vimeo_client: ReccVimeoClient,
    config: McrTeardownConfig,
):
    (video_uri, texttrack_uri) = vimeo_tasks.get_video_data(messenger, vimeo_client)

    config.vimeo_video_uri = video_uri
    config.vimeo_video_texttracks_uri = texttrack_uri


def disable_automatic_captions(
    config: McrTeardownConfig, vimeo_client: ReccVimeoClient, messenger: Messenger
):
    if config.vimeo_video_texttracks_uri is None:
        raise ValueError(
            "The link to the Vimeo video's captions is unknown (config.vimeo_video_texttracks_uri was not set)."
        )

    vimeo_tasks.disable_automatic_captions(
        texttracks_uri=config.vimeo_video_texttracks_uri,
        client=vimeo_client,
        messenger=messenger,
    )


def rename_video_on_vimeo(config: McrTeardownConfig, vimeo_client: ReccVimeoClient):
    video_uri = config.vimeo_video_uri
    if video_uri is None:
        raise ValueError(
            "The link to the Vimeo video is unknown (config.vimeo_video_uri was not set)."
        )

    vimeo_tasks.rename_video(video_uri, config.vimeo_video_title, vimeo_client)


def download_captions(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    with boxcast_client_factory.get_client() as client:
        boxcast_tasks.download_captions(
            client=client,
            captions_tab_url=config.live_event_captions_tab_url,
            download_path=config.captions_download_path,
            destination_path=config.original_captions_path,
            messenger=messenger,
        )


def copy_captions_to_without_worship(config: McrTeardownConfig, messenger: Messenger):
    if not config.original_captions_path.exists():
        raise ValueError(f"File '{config.original_captions_path}' does not exist.")

    # Copy the file first so that the new file isn't read-only
    shutil.copy(
        src=config.original_captions_path, dst=config.captions_without_worship_path
    )

    config.original_captions_path.chmod(stat.S_IREAD)


def copy_captions_to_final(config: McrTeardownConfig, messenger: Messenger):
    if not config.captions_without_worship_path.exists():
        raise ValueError(
            f"File '{config.captions_without_worship_path}' does not exist."
        )

    if config.final_captions_path.exists():
        messenger.log_problem(
            ProblemLevel.WARN,
            f"File '{config.final_captions_path}' already exists and will be overwritten",
        )

    # Copy the file first so that the new file isn't read-only
    shutil.copy(
        src=config.captions_without_worship_path, dst=config.final_captions_path
    )

    config.captions_without_worship_path.chmod(stat.S_IREAD)


def upload_captions_to_boxcast(
    boxcast_client_factory: BoxCastClientFactory, config: McrTeardownConfig
):
    with boxcast_client_factory.get_client() as client:
        boxcast_tasks.upload_captions_to_boxcast(
            client=client,
            url=config.boxcast_edit_captions_url,
            file_path=config.final_captions_path,
        )


def upload_captions_to_vimeo(
    config: McrTeardownConfig, vimeo_client: ReccVimeoClient, messenger: Messenger
):
    texttrack_uri = config.vimeo_video_texttracks_uri
    if texttrack_uri is None:
        raise ValueError(
            "The link to the Vimeo text track is unknown (config.vimeo_video_texttracks_uri was not set)."
        )

    vimeo_tasks.upload_captions_to_vimeo(
        config.final_captions_path, texttrack_uri, messenger, vimeo_client
    )
