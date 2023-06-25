import shutil
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from autochecklist.messenger import LogLevel, Messenger
from mcr_teardown.boxcast_client import BoxCastClient
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

_RETRY_SECONDS = 60
_SECONDS_PER_MINUTE = 60


def export_to_vimeo(client: BoxCastClient, event_url: str):
    client.get(event_url)

    # TODO: Add this to the BoxCastClient so that we can be sure that there's only one matching element
    wait = WebDriverWait(client, 60 * _SECONDS_PER_MINUTE)
    xpath = "//button[contains(., 'Download or Export Recording')]"
    download_or_export_button = wait.until(  # type: ignore
        EC.element_to_be_clickable((By.XPATH, xpath))  # type: ignore
    )
    if len(client.find_elements(By.XPATH, xpath)) > 1:
        raise ValueError(f"Multiple elements match XPATH '{xpath}'.")
    download_or_export_button.click()  # type: ignore

    vimeo_tab = client.find_single_element(
        By.XPATH, "//div[@id='headlessui-portal-root']//a[contains(., 'Vimeo')]"
    )
    vimeo_tab.click()

    user_dropdown = client.find_single_element(By.TAG_NAME, "select")
    user_dropdown_select = Select(user_dropdown)
    user_dropdown_select.select_by_visible_text("River's Edge")  # type: ignore

    vimeo_export_button = client.find_single_element(
        By.XPATH, "//button[contains(., 'Export To Vimeo')]"
    )
    vimeo_export_button.click()


def download_captions(
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


def upload_captions_to_boxcast(client: BoxCastClient, url: str, file_path: Path):
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
    # TODO: The button in the new UI says "Save Uploaded Caption File"
    xpath = "//button[contains(., 'Replace Captions with Upload')]"
    submit_button = wait.until(  # type: ignore
        EC.element_to_be_clickable((By.XPATH, xpath))  # type: ignore
    )
    if len(client.find_elements(By.XPATH, xpath)) > 1:
        raise ValueError(f"Multiple elements match XPATH '{xpath}'.")
    submit_button.click()  # type: ignore


def create_rebroadcast(
    rebroadcast_setup_url: str,
    source_broadcast_title: str,
    rebroadcast_title: str,
    start_datetime: datetime,
    client: BoxCastClient,
    messenger: Messenger,
    task_name: str,
):
    _get_rebroadcast_page(
        rebroadcast_setup_url, source_broadcast_title, client, messenger, task_name
    )

    try:
        _select_quick_entry_mode(client, messenger, task_name)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to check that the entry mode is 'Quick Entry': {e}",
            f"Failed to check that the entry mode is 'Quick Entry':\n{traceback.format_exc()}",
        )

    _set_event_name(rebroadcast_title, client)

    try:
        _clear_event_description(client)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to clear event description: {e}",
            f"Failed to clear event description:\n{traceback.format_exc()}",
        )

    try:
        _set_event_start_date(start_datetime.strftime("%m/%d/%Y"), client)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to set event start date: {e}",
            f"Failed to set event start date:\n{traceback.format_exc()}",
        )

    _set_event_start_time(start_datetime.strftime("%H:%M"), client)

    try:
        _make_event_non_recurring(client)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to check that the rebroadcast is non-recurring: {e}",
            f"Failed to check that the rebroadcast is non-recurring:\n{traceback.format_exc()}",
        )

    try:
        _make_event_public(client)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to check that the rebroadcast is public: {e}",
            f"Failed to check that the rebroadcast is public:\n{traceback.format_exc()}",
        )

    try:
        _clear_broadcast_destinations(client)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to check that there are no other destinations for this rebroadcast: {e}",
            f"Failed to check that there are no other destinations for this rebroadcast:\n{traceback.format_exc()}",
        )

    try:
        _show_advanced_settings(client)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to show the advanced settings: {e}",
            f"Failed to show the advanced settings:\n{traceback.format_exc()}",
        )

    try:
        _make_event_not_recorded(client)
    except Exception as e:
        messenger.log_separate(
            task_name,
            LogLevel.WARN,
            f"Failed to make rebroadcast not recorded: {e}",
            f"Failed to make rebroadcast not recorded:\n{traceback.format_exc()}",
        )

    _press_schedule_broadcast_button(client)

    # The website should redirect to the page for the newly-created rebroadcast after the button is pressed
    wait = WebDriverWait(client, timeout=10)
    wait.until(lambda driver: driver.current_url.startswith("https://dashboard.boxcast.com/broadcasts"))  # type: ignore


def _download_captions_to_downloads_folder(
    client: BoxCastClient,
    captions_tab_url: str,
):
    client.get(captions_tab_url)

    # TODO: Add this to the BoxCastClient so that we can be sure that there's only one matching element
    wait = WebDriverWait(client, 60 * _SECONDS_PER_MINUTE)
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


def _get_rebroadcast_page(
    rebroadcast_setup_url: str,
    expected_source_name: str,
    client: BoxCastClient,
    messenger: Messenger,
    task_name: str,
):
    """
    Gets the rebroadcast page and waits until the source broadcast is available.
    """
    while True:
        client.get(rebroadcast_setup_url)
        # Wait for page to fully load
        # TODO: Use Selenium's waits?
        time.sleep(5)

        source_broadcast_element = client.find_single_element(
            By.TAG_NAME, "recording-source-chooser"
        )
        if "Source Broadcast Unavailable" in source_broadcast_element.text:
            messenger.log(
                task_name,
                LogLevel.DEBUG,
                f"Source broadcast is not yet available. Retrying in {_RETRY_SECONDS} seconds.",
            )
            time.sleep(_RETRY_SECONDS)
        elif expected_source_name in source_broadcast_element.text:
            messenger.log(
                task_name,
                LogLevel.DEBUG,
                "Rebroadcast page loaded: source broadcast is as expected.",
            )
            return
        else:
            raise ValueError(
                "Unable to determine whether the source broadcast is available."
            )


def _select_quick_entry_mode(
    client: BoxCastClient, messenger: Messenger, task_name: str
):
    quick_entry_links = client.find_elements(
        By.XPATH, "//a[contains(., 'Quick Entry')]"
    )
    wizard_links = client.find_elements(By.XPATH, "//a[contains(., 'Wizard')]")

    if len(quick_entry_links) == 0 and len(wizard_links) == 1:
        messenger.log(task_name, LogLevel.DEBUG, "Already in 'Quick Entry' mode.")
    elif len(quick_entry_links) == 1 and len(wizard_links) == 0:
        messenger.log(
            task_name,
            LogLevel.DEBUG,
            "Currently in 'Wizard' mode. Switching to 'Quick Entry' mode.",
        )
        quick_entry_links[0].click()
    elif len(quick_entry_links) == 0 and len(wizard_links) == 0:
        raise ValueError("Could not determine entry mode because no links were found.")
    elif len(quick_entry_links) == 1 and len(wizard_links) == 1:
        raise ValueError(
            "Could not determine entry mode because links were found for both 'Quick Entry' and 'Wizard' modes."
        )
    else:
        raise ValueError(
            "Could not determine entry mode because there is more than one link containing 'Quick Entry' or more than one link containing 'Wizard'."
        )


def _set_event_name(name: str, client: BoxCastClient):
    broadcast_name_textbox = client.find_single_element(By.ID, "eventName")
    broadcast_name_textbox.clear()
    broadcast_name_textbox.send_keys(name)  # type: ignore


def _clear_event_description(client: BoxCastClient):
    description_textbox = client.find_single_element(By.ID, "eventDescription")
    description_textbox.clear()


def _set_event_start_date(date: str, client: BoxCastClient):
    start_date_input = client.find_single_element(
        By.XPATH, "//label[contains(., 'Start Date')]/..//input"
    )
    start_date_input.clear()
    start_date_input.send_keys(date)  # type: ignore


def _set_event_start_time(time: str, client: BoxCastClient):
    start_time_input = client.find_single_element(
        By.XPATH, "//label[contains(., 'Start Time')]/..//input"
    )
    start_time_input.clear()
    start_time_input.send_keys(time)  # type: ignore


def _make_event_non_recurring(client: BoxCastClient):
    recurring_broadcast_checkbox = client.find_single_element(
        By.XPATH,
        "//recurrence-pattern[contains(., 'Make This a Recurring Broadcast')]//i",
    )
    _set_checkbox_checked(recurring_broadcast_checkbox, False)


def _make_event_public(client: BoxCastClient):
    broadcast_public_button = client.find_single_element(
        By.XPATH,
        "//label[contains(text(), 'Broadcast Type')]/..//label[contains(., 'Public')]",
    )
    broadcast_public_button.click()


def _clear_broadcast_destinations(client: BoxCastClient):
    # TODO
    raise NotImplementedError("This operation is not yet implemented.")


def _show_advanced_settings(client: BoxCastClient):
    advanced_settings_elem = client.find_single_element(
        By.XPATH, "//a[contains(., 'Advanced Settings')]"
    )
    if "Show Advanced Settings" in advanced_settings_elem.text:
        advanced_settings_elem.click()
    elif "Hide Advanced Settings" in advanced_settings_elem.text:
        pass
    else:
        raise ValueError("Could not find link to reveal advanced settings.")


def _make_event_not_recorded(client: BoxCastClient):
    record_broadcast_checkbox = client.find_single_element(
        By.XPATH, "//label[contains(., 'Record Broadcast')]//i[1]"
    )
    _set_checkbox_checked(record_broadcast_checkbox, False)


def _press_schedule_broadcast_button(client: BoxCastClient):
    submit_button = client.find_single_element(
        By.XPATH, "//button[contains(., 'Schedule Broadcast')]"
    )
    submit_button.click()


def _set_checkbox_checked(checkbox: WebElement, should_check: bool):
    html_class = checkbox.get_attribute("class")  # type: ignore

    if "fa-check-square-o" in html_class:
        already_checked = True
    elif "fa-square-o" in html_class:
        already_checked = False
    else:
        raise ValueError(
            "Could not determine whether or not checkbox is currently checked."
        )

    if should_check != already_checked:
        checkbox.click()
