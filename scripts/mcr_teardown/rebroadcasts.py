import logging
import time
from datetime import datetime

from boxcast_client import BoxCastClient
from messenger import Messenger
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

_RETRY_SECONDS = 60


def create_rebroadcast(
    rebroadcast_setup_url: str,
    source_broadcast_title: str,
    rebroadcast_title: str,
    start_datetime: datetime,
    client: BoxCastClient,
    messenger: Messenger,
):
    _get_rebroadcast_page(
        rebroadcast_setup_url, source_broadcast_title, client, messenger
    )

    try:
        _select_quick_entry_mode(client, messenger)
    except Exception as e:
        messenger.log(
            logging.WARN, f"Failed to check that the entry mode is 'Quick Entry': {e}"
        )

    _set_event_name(rebroadcast_title, client)

    try:
        _clear_event_description(client)
    except Exception as e:
        messenger.log(logging.WARN, f"Failed to clear event description: {e}")

    try:
        _set_event_start_date(start_datetime.strftime("%m/%d/%Y"), client)
    except Exception as e:
        messenger.log(logging.WARN, f"Failed to set event start date: {e}")

    _set_event_start_time(start_datetime.strftime("%H:%M"), client)

    try:
        _make_event_non_recurring(client)
    except Exception as e:
        messenger.log(
            logging.WARN, f"Failed to check that the rebroadcast is non-recurring: {e}"
        )

    try:
        _make_event_public(client)
    except Exception as e:
        messenger.log(
            logging.WARN, f"Failed to check that the rebroadcast is public: {e}"
        )

    try:
        _clear_broadcast_destinations(client)
    except Exception as e:
        messenger.log(
            logging.WARN,
            f"Failed to check that there are no other destinations for this rebroadcast: {e}",
        )

    try:
        _show_advanced_settings(client)
    except Exception as e:
        messenger.log(logging.WARN, f"Failed to show the advanced settings: {e}")

    try:
        _make_event_not_recorded(client)
    except Exception as e:
        messenger.log(logging.WARN, f"Failed to make rebroadcast not recorded: {e}")

    _press_schedule_broadcast_button(client)


def _get_rebroadcast_page(
    rebroadcast_setup_url: str,
    expected_source_name: str,
    client: BoxCastClient,
    messenger: Messenger,
):
    """
    Gets the rebroadcast page and waits until the source broadcast is available.
    """
    while True:
        client.get(rebroadcast_setup_url)

        source_broadcast_element = client.find_single_element(
            By.TAG_NAME, "recording-source-chooser"
        )
        if "Source Broadcast Unavailable" in source_broadcast_element.text:
            messenger.log(
                logging.DEBUG,
                f"Source broadcast is not yet available. Retrying in {_RETRY_SECONDS} seconds.",
            )
            time.sleep(_RETRY_SECONDS)
        elif expected_source_name in source_broadcast_element.text:
            messenger.log(
                logging.DEBUG,
                "Rebroadcast page loaded: source broadcast is as expected.",
            )
            return
        else:
            raise ValueError(
                "Unable to determine whether the source broadcast is available."
            )


def _select_quick_entry_mode(client: BoxCastClient, messenger: Messenger):
    quick_entry_links = client.find_elements(
        By.XPATH, "//a[contains(., 'Quick Entry')]"
    )
    wizard_links = client.find_elements(By.XPATH, "//a[contains(., 'Wizard')]")

    if len(quick_entry_links) == 0 and len(wizard_links) == 1:
        messenger.log(logging.DEBUG, "Already in 'Quick Entry' mode.")
    elif len(quick_entry_links) == 1 and len(wizard_links) == 0:
        messenger.log(
            logging.DEBUG,
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
        # TODO: This selector is garbage
        "//span[contains(., 'Make This a Recurring Broadcast')]/*[1]",
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
        By.XPATH, "//label[contains(., 'Record Broadcast')]/*[1]"
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
