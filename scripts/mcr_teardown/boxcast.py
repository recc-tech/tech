import shutil
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from autochecklist import LogLevel, Messenger
from credentials import Credential, CredentialStore
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

_RETRY_SECONDS = 60
_SECONDS_PER_MINUTE = 60


class BoxCastClient(WebDriver):
    _TASK_NAME = "BOXCAST CLIENT"
    _LOGIN_URL = "https://login.boxcast.com/login"

    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        headless: bool = True,
    ):
        options = Options()
        if headless:
            options.add_argument("-headless")  # type: ignore
        super().__init__(options=options)  # type: ignore

        self._messenger = messenger
        self._credential_store = credential_store

        self._login_with_retries(
            target_url="https://dashboard.boxcast.com/broadcasts", max_attempts=3
        )

    def get(self, url: str):
        redirect_timeout = 10
        super().get(url)
        wait = WebDriverWait(self, timeout=redirect_timeout)
        wait.until(  # type: ignore
            lambda driver: driver.current_url in [url, BoxCastClient._LOGIN_URL],  # type: ignore
            message=f"Did not get redirected to the target page ({url}) or to the login page within {redirect_timeout} seconds.",
        )

        if self.current_url.startswith(BoxCastClient._LOGIN_URL):
            self._login_with_retries(target_url=url, max_attempts=3)

    def _login_with_retries(self, target_url: str, max_attempts: int):
        max_seconds_to_redirect = 10
        wait = WebDriverWait(self, timeout=max_seconds_to_redirect)
        for attempt_num in range(1, max_attempts + 1):
            # For some reason, the login often fails if we try going to the target page and are redirected to the login
            # page. On the other hand, going to the login page, logging in, and only then going to the target page
            # seems to work.
            super().get(BoxCastClient._LOGIN_URL)
            username = self._credential_store.get(
                Credential.BOXCAST_USERNAME, force_user_input=attempt_num > 1
            )
            password = self._credential_store.get(
                Credential.BOXCAST_PASSWORD,
                force_user_input=attempt_num > 1,
            )
            self._complete_login_form(username, password)

            try:
                wait.until(  # type: ignore
                    lambda driver: driver.current_url != BoxCastClient._LOGIN_URL,  # type: ignore
                    message=f"Login failed: still on the login page after {max_seconds_to_redirect} seconds.",
                )
                # TODO: This seems to fail when it comes to the rebroadcasts. The driver just stays on the home page
                super().get(target_url)
                wait.until(  # type: ignore
                    lambda driver: driver.current_url == target_url,  # type: ignore
                    message=f"Could not get target page ({target_url}) within {max_seconds_to_redirect} seconds.",
                )
                return
            except TimeoutException:
                self._messenger.log_separate(
                    self._TASK_NAME,
                    LogLevel.WARN,
                    f"Failed to log in to BoxCast (attempt {attempt_num}/{max_attempts}).",
                    f"Failed to log in to BoxCast (attempt {attempt_num}/{max_attempts}).\n{traceback.format_exc()}",
                )
        raise RuntimeError(f"Failed to log in to BoxCast ({max_attempts} attempts).")

    def _complete_login_form(self, username: str, password: str):
        email_textbox = self.wait_for_single_element(By.ID, "email", timeout=10)
        email_textbox.send_keys(username)  # type: ignore

        password_textbox = self.wait_for_single_element(By.ID, "password")
        password_textbox.send_keys(password)  # type: ignore

        login_button = self.wait_for_single_element(
            By.XPATH, "//input[@value='Log In'][@type='submit']"
        )
        login_button.click()

    def wait_for_single_element(
        self,
        by: str,
        value: str,
        # This seems like a reasonably safe amount of time to wait if you expect the element to already be loaded,
        # but potentially be obscured by another element (e.g., a dropdown menu)
        timeout: float = 5,
        # Whether the element needs to be clickable
        clickable: bool = True,
    ) -> WebElement:
        ec = EC.element_to_be_clickable((by, value)) if clickable else EC.presence_of_element_located((by, value))  # type: ignore

        wait = WebDriverWait(self, timeout=timeout)
        try:
            wait.until(  # type: ignore
                ec,
            )
        except TimeoutException:
            # The error might be because there are no matches, but it could also be because there are multiple matches and the first one isn't clickable!
            elements = self.find_elements(by, value)
            if len(elements) == 0:
                raise NoSuchElementException(
                    f"No element found for the given criteria (by = {by}, value = '{value}')."
                )
            elif len(elements) == 1:
                raise ValueError(
                    f"An element was found for the given criteria (by = {by}, value = '{value}'), but it does not seem to be clickable."
                )
            else:
                raise ValueError(
                    f"{len(elements)} elements matched the given criteria (by = {by}, value = '{value}')."
                )

        # Wait to see if duplicate elements appear
        time.sleep(1)

        elements = self.find_elements(by, value)
        if len(elements) == 0:
            raise NoSuchElementException(
                f"No element found for the given criteria (by = {by}, value = '{value}')."
            )
        elif len(elements) == 1:
            return elements[0]
        else:
            raise ValueError(
                f"{len(elements)} elements matched the given criteria (by = {by}, value = '{value}')."
            )


class BoxCastClientFactory:
    def __init__(
        self, messenger: Messenger, credential_store: CredentialStore, headless: bool
    ):
        self._messenger = messenger
        self._credential_store = credential_store
        self._headless = headless

    def get_client(self):
        return BoxCastClient(
            messenger=self._messenger,
            credential_store=self._credential_store,
            headless=self._headless,
        )


# TODO: Use the new BoxCast UI
def export_to_vimeo(client: BoxCastClient, event_url: str):
    client.get(event_url)

    download_or_export_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Download or Export Recording')]",
        timeout=60 * _SECONDS_PER_MINUTE,
    )
    download_or_export_button.click()  # type: ignore

    vimeo_tab = client.wait_for_single_element(
        By.XPATH, "//div[@id='headlessui-portal-root']//a[contains(., 'Vimeo')]"
    )
    vimeo_tab.click()

    user_dropdown_label = client.wait_for_single_element(
        By.XPATH, "//label[contains(., 'Export as User')]"
    )
    user_dropdown_id = user_dropdown_label.get_attribute("for")  # type: ignore

    user_dropdown = client.wait_for_single_element(
        By.XPATH, f"//select[@id='{user_dropdown_id}']"
    )
    user_dropdown_select = Select(user_dropdown)
    user_dropdown_select.select_by_visible_text("River's Edge")  # type: ignore

    vimeo_export_button = client.wait_for_single_element(
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

    # There is also a settings "button" in the sidebar, but it is represented
    # with an <a> tag rather than a <button> tag. Just in case, check that the
    # button selected here is not in the sidebar.
    settings_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Settings')][not(ancestor::nav)]",
        timeout=10,
    )
    settings_button.click()  # type: ignore

    replace_captions_option = client.wait_for_single_element(
        By.XPATH, "//button[contains(., 'Replace Captions with WebVTT File')]"
    )
    replace_captions_option.click()

    file_input = client.wait_for_single_element(
        By.XPATH, "//input[@type='file'][contains(@accept, '.vtt')]", clickable=False
    )
    file_input.send_keys(str(file_path))  # type: ignore

    submit_button = client.wait_for_single_element(
        By.XPATH, "//button[contains(., 'Save Uploaded Caption File')]", timeout=10
    )
    submit_button.click()  # type: ignore


# TODO: Use the new BoxCast UI
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
    expected_prefix = "https://dashboard.boxcast.com/broadcasts"
    redirect_timeout = 10
    wait = WebDriverWait(client, timeout=redirect_timeout)
    wait.until(  # type: ignore
        lambda driver: driver.current_url.startswith(expected_prefix),  # type: ignore
        message=f"Did not get redirected to the expected page (starting with {expected_prefix}) within {redirect_timeout} seconds.",
    )


def _download_captions_to_downloads_folder(
    client: BoxCastClient,
    captions_tab_url: str,
):
    client.get(captions_tab_url)

    download_captions_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Download Captions')]",
        timeout=60 * _SECONDS_PER_MINUTE,
    )
    download_captions_button.click()  # type: ignore

    vtt_download_button = client.wait_for_single_element(
        By.XPATH, "//button[contains(., 'WebVTT File (.vtt)')]", timeout=1
    )
    vtt_download_button.click()


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
    Get the rebroadcast page and wait until the source broadcast is available.
    """
    while True:
        client.get(rebroadcast_setup_url)

        source_broadcast_element = client.wait_for_single_element(
            By.TAG_NAME, "recording-source-chooser", timeout=10
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
    broadcast_name_textbox = client.wait_for_single_element(By.ID, "eventName")
    broadcast_name_textbox.clear()
    broadcast_name_textbox.send_keys(name)  # type: ignore


def _clear_event_description(client: BoxCastClient):
    description_textbox = client.wait_for_single_element(By.ID, "eventDescription")
    description_textbox.clear()


def _set_event_start_date(date: str, client: BoxCastClient):
    start_date_input = client.wait_for_single_element(
        By.XPATH, "//label[contains(., 'Start Date')]/..//input"
    )
    start_date_input.clear()
    start_date_input.send_keys(date)  # type: ignore


def _set_event_start_time(time: str, client: BoxCastClient):
    start_time_input = client.wait_for_single_element(
        By.XPATH, "//label[contains(., 'Start Time')]/..//input"
    )
    start_time_input.clear()
    start_time_input.send_keys(time)  # type: ignore


def _make_event_non_recurring(client: BoxCastClient):
    recurring_broadcast_checkbox = client.wait_for_single_element(
        By.XPATH,
        "//recurrence-pattern[contains(., 'Make This a Recurring Broadcast')]//i",
    )
    _set_checkbox_checked(recurring_broadcast_checkbox, False)


def _make_event_public(client: BoxCastClient):
    broadcast_public_button = client.wait_for_single_element(
        By.XPATH,
        "//label[contains(text(), 'Broadcast Type')]/..//label[contains(., 'Public')]",
    )
    broadcast_public_button.click()


def _clear_broadcast_destinations(client: BoxCastClient):
    # TODO
    raise NotImplementedError("This operation is not yet implemented.")


def _show_advanced_settings(client: BoxCastClient):
    advanced_settings_elem = client.wait_for_single_element(
        By.XPATH, "//a[contains(., 'Advanced Settings')]"
    )
    if "Show Advanced Settings" in advanced_settings_elem.text:
        advanced_settings_elem.click()
    elif "Hide Advanced Settings" in advanced_settings_elem.text:
        pass
    else:
        raise ValueError("Could not find link to reveal advanced settings.")


def _make_event_not_recorded(client: BoxCastClient):
    record_broadcast_checkbox = client.wait_for_single_element(
        By.XPATH, "//label[contains(., 'Record Broadcast')]//i[1]"
    )
    _set_checkbox_checked(record_broadcast_checkbox, False)


def _press_schedule_broadcast_button(client: BoxCastClient):
    submit_button = client.wait_for_single_element(
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
