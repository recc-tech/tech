import shutil
import stat
import time
from datetime import datetime, timedelta
from pathlib import Path

import mcr_teardown.rebroadcasts as rebroadcasts
import mcr_teardown.vimeo as recc_vimeo
from boxcast_client import BoxCastClient, BoxCastClientFactory
from mcr_teardown.config import McrTeardownConfig
from messenger import LogLevel, Messenger
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from vimeo import VimeoClient  # type: ignore

SECONDS_PER_MINUTE = 60


def create_rebroadcast_1pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
    task_name: str,
):
    with boxcast_client_factory.get_client() as client:
        rebroadcasts.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=datetime.now().replace(hour=13, minute=0, second=0),
            client=client,
            messenger=messenger,
            task_name=task_name,
        )


def create_rebroadcast_5pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
    task_name: str,
):
    with boxcast_client_factory.get_client() as client:
        rebroadcasts.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=datetime.now().replace(hour=17, minute=0, second=0),
            client=client,
            messenger=messenger,
            task_name=task_name,
        )


def create_rebroadcast_7pm(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
    task_name: str,
):
    with boxcast_client_factory.get_client() as client:
        rebroadcasts.create_rebroadcast(
            rebroadcast_setup_url=config.rebroadcast_setup_url,
            source_broadcast_title=config.live_event_title,
            rebroadcast_title=config.rebroadcast_title,
            start_datetime=datetime.now().replace(hour=19, minute=0, second=0),
            client=client,
            messenger=messenger,
            task_name=task_name,
        )


def export_to_vimeo(
    boxcast_client_factory: BoxCastClientFactory, config: McrTeardownConfig
):
    with boxcast_client_factory.get_client() as client:
        _export_to_vimeo(client=client, event_url=config.live_event_url)


def get_vimeo_video_data(
    messenger: Messenger,
    vimeo_client: VimeoClient,
    config: McrTeardownConfig,
    task_name: str,
):
    (video_uri, texttrack_uri) = recc_vimeo.get_video_data(
        messenger, vimeo_client, task_name
    )

    config.vimeo_video_uri = video_uri
    config.vimeo_video_texttracks_uri = texttrack_uri


def rename_video_on_vimeo(config: McrTeardownConfig, vimeo_client: VimeoClient):
    video_uri = config.vimeo_video_uri
    if video_uri is None:
        raise ValueError(
            "The link to the Vimeo video is unknown (config.vimeo_video_uri was not set)."
        )

    recc_vimeo.rename_video(video_uri, config.vimeo_video_title, vimeo_client)


def download_captions(
    boxcast_client_factory: BoxCastClientFactory,
    config: McrTeardownConfig,
    messenger: Messenger,
    task_name: str,
):
    with boxcast_client_factory.get_client() as client:
        _download_captions(
            client=client,
            captions_tab_url=config.live_event_captions_tab_url,
            download_path=config.captions_download_path,
            destination_path=config.original_captions_path,
            messenger=messenger,
            task_name=task_name,
        )


def copy_captions_to_without_worship(
    config: McrTeardownConfig, messenger: Messenger, task_name: str
):
    _mark_read_only_and_copy(
        config.original_captions_path,
        config.captions_without_worship_path,
        messenger,
        task_name,
    )


def copy_captions_to_final(
    config: McrTeardownConfig, messenger: Messenger, task_name: str
):
    _mark_read_only_and_copy(
        config.captions_without_worship_path,
        config.final_captions_path,
        messenger,
        task_name,
    )


def upload_captions_to_boxcast(
    boxcast_client_factory: BoxCastClientFactory, config: McrTeardownConfig
):
    with boxcast_client_factory.get_client() as client:
        _upload_captions_to_boxcast(
            client=client,
            url=config.boxcast_edit_captions_url,
            file_path=config.final_captions_path,
        )


def upload_captions_to_vimeo(
    config: McrTeardownConfig,
    vimeo_client: VimeoClient,
    messenger: Messenger,
    task_name: str,
):
    texttrack_uri = config.vimeo_video_texttracks_uri
    if texttrack_uri is None:
        raise ValueError(
            "The link to the Vimeo text track is unknown (config.vimeo_video_texttracks_uri was not set)."
        )

    recc_vimeo.upload_captions_to_vimeo(
        config.final_captions_path, texttrack_uri, messenger, vimeo_client, task_name
    )


def _mark_read_only_and_copy(
    source: Path, destination: Path, messenger: Messenger, task_name: str
):
    if not source.exists():
        raise ValueError(f"File '{source}' does not exist.")

    if destination.exists():
        messenger.log(
            task_name,
            LogLevel.WARN,
            f"File '{destination}' already exists and will be overwritten.",
        )

    # Copy the file
    shutil.copy(src=source, dst=destination)
    messenger.log(task_name, LogLevel.DEBUG, f"Copied '{source}' to '{destination}'.")

    # Mark the original file as read-only
    source.chmod(stat.S_IREAD)
    messenger.log(task_name, LogLevel.DEBUG, f"Marked '{source}' as read-only.")


def _export_to_vimeo(client: BoxCastClient, event_url: str):
    client.get(event_url)

    # TODO: Add this to the BoxCastClient so that we can be sure that there's only one matching element
    wait = WebDriverWait(client, 60 * SECONDS_PER_MINUTE)
    xpath = "//button[contains(., 'Download or Export Recording')]"
    download_or_export_button = wait.until(  # type: ignore
        EC.element_to_be_clickable((By.XPATH, xpath))  # type: ignore
    )
    if len(client.find_elements(By.XPATH, xpath)) > 1:
        raise ValueError(f"Multiple elements match XPATH '{xpath}'.")
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


def _download_captions(
    client: BoxCastClient,
    captions_tab_url: str,
    download_path: Path,
    destination_path: Path,
    messenger: Messenger,
    task_name: str,
):
    _download_captions_to_downloads_folder(client, captions_tab_url)
    _move_captions_to_captions_folder(
        download_path, destination_path, messenger, task_name
    )


def _download_captions_to_downloads_folder(
    client: BoxCastClient,
    captions_tab_url: str,
):
    client.get(captions_tab_url)

    # TODO: Add this to the BoxCastClient so that we can be sure that there's only one matching element
    wait = WebDriverWait(client, 60 * SECONDS_PER_MINUTE)
    xpath = "//button[contains(., 'Download Captions')]"
    download_captions_button = wait.until(  # type: ignore
        EC.element_to_be_clickable((By.XPATH, xpath))  # type: ignore
    )
    if len(client.find_elements(By.XPATH, xpath)) > 1:
        raise ValueError(f"Multiple elements match XPATH '{xpath}'.")
    download_captions_button.click()  # type: ignore

    vtt_download_link = client.find_single_element(
        By.XPATH, "//a[contains(., 'VTT File (.vtt)')]"
    )
    vtt_download_link.click()


def _move_captions_to_captions_folder(
    download_path: Path, destination_path: Path, messenger: Messenger, task_name: str
):
    _wait_for_file_to_exist(download_path, timeout=timedelta(seconds=60))

    if destination_path.exists():
        messenger.log(
            task_name,
            LogLevel.WARN,
            f"File '{destination_path}' already exists and will be overwritten.",
        )
    else:
        destination_path.parent.mkdir(exist_ok=True, parents=True)

    shutil.move(download_path, destination_path)


def _wait_for_file_to_exist(path: Path, timeout: timedelta):
    wait_start = datetime.now()
    while True:
        if path.exists():
            return
        if datetime.now() - wait_start > timeout:
            raise FileNotFoundError(f"Did not find file at '{path}' within {timeout}.")
        time.sleep(1)


def _upload_captions_to_boxcast(client: BoxCastClient, url: str, file_path: Path):
    client.get(url)

    # TODO: Add this to the BoxCastClient so that we can be sure that there's only one matching element
    wait = WebDriverWait(client, timeout=10)
    # The id 'btn-append-to-body' is not unique on the page D:<<<
    xpath = "//button[@id='btn-append-to-body'][@type='button']/i[contains(@class, 'fa-cog')]"
    cog_button = wait.until(  # type: ignore
        EC.element_to_be_clickable((By.XPATH, xpath))  # type: ignore
    )
    if len(client.find_elements(By.XPATH, xpath)) > 1:
        raise ValueError(f"Multiple elements match XPATH '{xpath}'.")
    cog_button.click()  # type: ignore

    replace_captions_option = client.find_single_element(
        By.XPATH, "//a[contains(., 'Replace Captions with WebVTT File')]"
    )
    replace_captions_option.click()

    file_input = client.find_single_element(By.XPATH, "//input[@type='file']")
    file_input.send_keys(str(file_path))  # type: ignore

    # TODO: Add this to the BoxCastClient so that we can be sure that there's only one matching element
    xpath = "//button[contains(., 'Replace Captions with Upload')]"
    submit_button = wait.until(  # type: ignore
        EC.element_to_be_clickable((By.XPATH, xpath))  # type: ignore
    )
    if len(client.find_elements(By.XPATH, xpath)) > 1:
        raise ValueError(f"Multiple elements match XPATH '{xpath}'.")
    submit_button.click()  # type: ignore
