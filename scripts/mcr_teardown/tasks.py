import logging
import shutil
import stat
from datetime import datetime
from pathlib import Path

import mcr_teardown.rebroadcasts as rebroadcasts
import mcr_teardown.vimeo as recc_vimeo
from boxcast_client import BoxCastClient, BoxCastClientFactory
from config import Config
from messenger import Messenger
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from vimeo import VimeoClient  # type: ignore

SECONDS_PER_MINUTE = 60


def create_rebroadcast_1pm(
    boxcast_client_factory: BoxCastClientFactory, config: Config, messenger: Messenger
):
    rebroadcasts.create_rebroadcast(
        rebroadcast_setup_url=config.rebroadcast_setup_url,
        source_broadcast_title=config.live_event_title,
        rebroadcast_title=config.rebroadcast_title,
        start_datetime=datetime.now().replace(hour=13, minute=0, second=0),
        client=boxcast_client_factory.get_client(),
        messenger=messenger,
    )


def create_rebroadcast_5pm(
    boxcast_client_factory: BoxCastClientFactory, config: Config, messenger: Messenger
):
    rebroadcasts.create_rebroadcast(
        rebroadcast_setup_url=config.rebroadcast_setup_url,
        source_broadcast_title=config.live_event_title,
        rebroadcast_title=config.rebroadcast_title,
        start_datetime=datetime.now().replace(hour=17, minute=0, second=0),
        client=boxcast_client_factory.get_client(),
        messenger=messenger,
    )


def create_rebroadcast_7pm(
    boxcast_client_factory: BoxCastClientFactory, config: Config, messenger: Messenger
):
    rebroadcasts.create_rebroadcast(
        rebroadcast_setup_url=config.rebroadcast_setup_url,
        source_broadcast_title=config.live_event_title,
        rebroadcast_title=config.rebroadcast_title,
        start_datetime=datetime.now().replace(hour=19, minute=0, second=0),
        client=boxcast_client_factory.get_client(),
        messenger=messenger,
    )


def export_to_vimeo(boxcast_client_factory: BoxCastClientFactory, config: Config):
    _export_to_vimeo(
        client=boxcast_client_factory.get_client(), event_url=config.live_event_url
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

    recc_vimeo.rename_video(video_uri, config.vimeo_video_title, vimeo_client)


def copy_captions_original_to_without_worship(messenger: Messenger, config: Config):
    _mark_read_only_and_copy(
        config.original_captions_path,
        config.captions_without_worship_path,
        messenger,
    )


def copy_captions_without_worship_to_final(messenger: Messenger, config: Config):
    _mark_read_only_and_copy(
        config.captions_without_worship_path,
        config.final_captions_path,
        messenger,
    )


def upload_captions_to_vimeo(
    config: Config, messenger: Messenger, vimeo_client: VimeoClient
):
    texttrack_uri = config.vimeo_video_texttracks_uri
    if texttrack_uri is None:
        raise ValueError(
            "The link to the Vimeo text track is unknown (config.vimeo_video_texttracks_uri was not set)."
        )

    recc_vimeo.upload_captions_to_vimeo(
        config.final_captions_path, texttrack_uri, messenger, vimeo_client
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


def _export_to_vimeo(client: BoxCastClient, event_url: str):
    client.get(event_url)

    wait = WebDriverWait(client, 60 * SECONDS_PER_MINUTE)
    download_or_export_button = wait.until(  # type: ignore
        EC.element_to_be_clickable(  # type: ignore
            (By.XPATH, "//button[contains(., 'Download or Export Recording')]")
        )
    )
    download_or_export_button.click()  # type: ignore

    vimeo_tab = client.find_single_element(
        By.XPATH, "//div[contains(@class, 'modal-header')]/ol/li[contains(., 'Vimeo')]"
    )
    vimeo_tab.click()

    user_dropdown = client.find_single_element(By.ID, "vimeo_user")
    user_dropdown_select = Select(user_dropdown)
    user_dropdown_select.select_by_visible_text("River's Edge")  # type: ignore

    vimeo_export_button = client.find_single_element(
        By.XPATH, "//button[contains(., 'Export To Vimeo')]"
    )
    vimeo_export_button.click()
