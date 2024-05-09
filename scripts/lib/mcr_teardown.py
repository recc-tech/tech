import shutil
import stat
from datetime import datetime, timedelta

import autochecklist
import external_services.boxcast as boxcast_tasks
import lib
import webvtt
from autochecklist import Messenger, TaskStatus
from config import Config, McrTeardownConfig
from external_services import BoxCastApiClient, BoxCastClientFactory, ReccVimeoClient


def wait_for_BoxCast_recording(
    client: BoxCastApiClient, messenger: Messenger, config: Config
) -> None:
    cancel_token = messenger.allow_cancel()
    retry_delay = timedelta(seconds=60)
    while True:
        broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
        if broadcast is not None:
            messenger.log_debug(f"Today's broadcast ID is {broadcast.id}.")
            return
        else:
            messenger.log_status(
                TaskStatus.RUNNING,
                f"The BoxCast recording does not seem to be ready as of {datetime.now().strftime('%H:%M:%S')}."
                f" Retrying in {retry_delay.total_seconds():.2f} seconds.",
            )
            autochecklist.sleep_attentively(
                timeout=retry_delay, cancellation_token=cancel_token
            )


def create_rebroadcast_1pm(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.schedule_rebroadcast(
            broadcast_id=broadcast.id,
            name=config.rebroadcast_title,
            start=config.start_time.replace(hour=13, minute=0, second=0),
        )


def create_rebroadcast_5pm(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.schedule_rebroadcast(
            broadcast_id=broadcast.id,
            name=config.rebroadcast_title,
            start=config.start_time.replace(hour=17, minute=0, second=0),
        )


def create_rebroadcast_7pm(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.schedule_rebroadcast(
            broadcast_id=broadcast.id,
            name=config.rebroadcast_title,
            start=config.start_time.replace(hour=19, minute=0, second=0),
        )


def export_to_Vimeo(
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


def rename_video_on_Vimeo(
    config: McrTeardownConfig, vimeo_client: ReccVimeoClient, messenger: Messenger
):
    (video_uri, _) = vimeo_client.get_video_data(messenger.allow_cancel())
    vimeo_client.rename_video(video_uri, config.vimeo_video_title)


def download_captions(client: BoxCastApiClient, config: McrTeardownConfig) -> None:
    broadcast = client.find_main_broadcast_by_date(dt=config.start_time.date())
    if broadcast is None:
        raise ValueError("No broadcast found on BoxCast.")
    else:
        client.download_captions(
            broadcast_id=broadcast.id,
            path=config.original_captions_file,
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


def upload_captions_to_BoxCast(
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


def upload_captions_to_Vimeo(
    messenger: Messenger, vimeo_client: ReccVimeoClient, config: McrTeardownConfig
):
    (_, texttrack_uri) = vimeo_client.get_video_data(messenger.allow_cancel())
    vimeo_client.upload_captions_to_vimeo(config.final_captions_file, texttrack_uri)
