import shutil
import stat

import external_services.boxcast as boxcast_tasks
import lib
import webvtt
from autochecklist import Messenger
from config import McrTeardownConfig
from external_services.boxcast import BoxCastClientFactory
from external_services.vimeo import ReccVimeoClient


def create_rebroadcast_1pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    cancellation_token = messenger.allow_cancel()
    with boxcast_client_factory.get_client(cancellation_token) as client:
        boxcast_tasks.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=config.start_time.replace(hour=13, minute=0, second=0),
            client=client,
            messenger=messenger,
            cancellation_token=cancellation_token,
        )


def create_rebroadcast_5pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    cancellation_token = messenger.allow_cancel()
    with boxcast_client_factory.get_client(cancellation_token) as client:
        boxcast_tasks.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=config.start_time.replace(hour=17, minute=0, second=0),
            client=client,
            messenger=messenger,
            cancellation_token=cancellation_token,
        )


def create_rebroadcast_7pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    cancellation_token = messenger.allow_cancel()
    with boxcast_client_factory.get_client(cancellation_token) as client:
        boxcast_tasks.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=config.start_time.replace(hour=19, minute=0, second=0),
            client=client,
            messenger=messenger,
            cancellation_token=cancellation_token,
        )


def export_to_vimeo(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    cancellation_token = messenger.allow_cancel()
    with boxcast_client_factory.get_client(cancellation_token) as client:
        boxcast_tasks.export_to_vimeo(
            client=client,
            event_url=config.live_event_url,
            cancellation_token=cancellation_token,
        )


def disable_automatic_captions(vimeo_client: ReccVimeoClient, messenger: Messenger):
    cancellation_token = messenger.allow_cancel()
    (_, texttrack_uri) = vimeo_client.get_video_data(cancellation_token)
    vimeo_client.disable_automatic_captions(
        texttracks_uri=texttrack_uri, cancellation_token=cancellation_token
    )


def rename_video_on_vimeo(
    config: McrTeardownConfig, vimeo_client: ReccVimeoClient, messenger: Messenger
):
    (video_uri, _) = vimeo_client.get_video_data(messenger.allow_cancel())
    vimeo_client.rename_video(video_uri, config.vimeo_video_title)


def download_captions(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    cancellation_token = messenger.allow_cancel()
    with boxcast_client_factory.get_client(cancellation_token) as client:
        boxcast_tasks.download_captions(
            client=client,
            captions_tab_url=config.live_event_captions_tab_url,
            download_path=config.captions_download_path,
            destination_path=config.original_captions_file,
            cancellation_token=cancellation_token,
        )


def copy_captions_to_final(config: McrTeardownConfig):
    if not config.original_captions_file.exists():
        raise ValueError(f"File '{config.original_captions_file}' does not exist.")
    # Copy the file first so that the new file isn't read-only
    shutil.copy(src=config.original_captions_file, dst=config.final_captions_file)
    config.original_captions_file.chmod(stat.S_IREAD)


def remove_worship_captions(config: McrTeardownConfig):
    original_vtt = webvtt.read(config.final_captions_file)
    final_vtt = lib.remove_worship_captions(original_vtt)
    final_vtt.save(config.final_captions_file)


def upload_captions_to_boxcast(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
):
    cancellation_token = messenger.allow_cancel()
    with boxcast_client_factory.get_client(cancellation_token) as client:
        boxcast_tasks.upload_captions_to_boxcast(
            client=client,
            url=config.boxcast_edit_captions_url,
            file_path=config.final_captions_file,
            cancellation_token=cancellation_token,
        )


def upload_captions_to_vimeo(
    messenger: Messenger, vimeo_client: ReccVimeoClient, config: McrTeardownConfig
):
    (_, texttrack_uri) = vimeo_client.get_video_data(messenger.allow_cancel())
    vimeo_client.upload_captions_to_vimeo(config.final_captions_file, texttrack_uri)
