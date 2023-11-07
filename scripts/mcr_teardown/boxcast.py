import shutil
import time
import traceback
from datetime import datetime, timedelta
from inspect import cleandoc
from pathlib import Path
from typing import Optional

import autochecklist
from autochecklist import (
    CancellationToken,
    Messenger,
    ProblemLevel,
    TaskStatus,
    sleep_attentively,
)
from common import Credential, CredentialStore, InputPolicy, ReccWebDriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.select import Select


class BoxCastClient(ReccWebDriver):
    _LOGIN_URL = "https://login.boxcast.com/login"

    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        cancellation_token: Optional[CancellationToken],
        headless: bool = True,
        lazy_login: bool = False,
        log_file: Optional[Path] = None,
    ):
        super().__init__(headless=headless, log_file=log_file)

        self._messenger = messenger
        self._credential_store = credential_store

        if not lazy_login:
            self._login_with_retries(
                target_url="https://dashboard.boxcast.com/broadcasts",
                max_attempts=3,
                cancellation_token=cancellation_token,
            )

    def get(self, url: str, cancellation_token: Optional[CancellationToken] = None):
        super().get(url)
        redirect_timeout = 10
        self.wait(
            condition=lambda driver: driver.current_url
            in [url, BoxCastClient._LOGIN_URL],
            timeout=timedelta(seconds=redirect_timeout),
            message=f"Did not get redirected to the target page ({url}) or to the login page within {redirect_timeout} seconds.",
            cancellation_token=cancellation_token,
        )

        if self.current_url.startswith(BoxCastClient._LOGIN_URL):
            self._login_with_retries(
                target_url=url, max_attempts=3, cancellation_token=cancellation_token
            )

    def _login_with_retries(
        self,
        target_url: str,
        max_attempts: int,
        cancellation_token: Optional[CancellationToken],
    ):
        self._messenger.log_status(TaskStatus.RUNNING, "Logging into BoxCast...")
        max_seconds_to_redirect = 10
        for attempt_num in range(1, max_attempts + 1):
            # For some reason, the login often fails if we try going to the target page and are redirected to the login
            # page. On the other hand, going to the login page, logging in, and only then going to the target page
            # seems to work.
            super().get(BoxCastClient._LOGIN_URL)
            credentials = self._credential_store.get_multiple(
                prompt="Enter the BoxCast credentials.",
                credentials=[Credential.BOXCAST_USERNAME, Credential.BOXCAST_PASSWORD],
                request_input=(
                    InputPolicy.ALWAYS if attempt_num > 1 else InputPolicy.AS_REQUIRED
                ),
            )
            username = credentials[Credential.BOXCAST_USERNAME]
            password = credentials[Credential.BOXCAST_PASSWORD]
            self._complete_login_form(username, password, cancellation_token)

            try:
                self.wait(
                    condition=(
                        lambda driver: driver.current_url != BoxCastClient._LOGIN_URL
                    ),
                    timeout=timedelta(seconds=max_seconds_to_redirect),
                    message=f"Login failed: still on the login page after {max_seconds_to_redirect} seconds.",
                    cancellation_token=cancellation_token,
                )
                super().get(target_url)
                self.wait(
                    condition=lambda driver: driver.current_url == target_url,
                    timeout=timedelta(seconds=max_seconds_to_redirect),
                    message=f"Could not get target page ({target_url}) within {max_seconds_to_redirect} seconds.",
                    cancellation_token=cancellation_token,
                )
                self._messenger.log_status(
                    TaskStatus.RUNNING,
                    "Successfully logged into BoxCast.",
                )
                return
            except TimeoutException:
                self._messenger.log_debug(
                    cleandoc(
                        f"""
                        Failed to log in to BoxCast (attempt {attempt_num}/{max_attempts}).\n
                        {traceback.format_exc()}
                        """
                    ),
                )
        raise RuntimeError(f"Failed to log in to BoxCast ({max_attempts} attempts).")

    def _complete_login_form(
        self,
        username: str,
        password: str,
        cancellation_token: Optional[CancellationToken],
    ):
        email_textbox = self.wait_for_single_element(
            By.ID,
            "email",
            cancellation_token=cancellation_token,
            timeout=timedelta(seconds=10),
        )
        _send_keys(email_textbox, username)

        password_textbox = self.wait_for_single_element(
            By.ID, "password", cancellation_token=cancellation_token
        )
        _send_keys(password_textbox, password)

        login_button = self.wait_for_single_element(
            By.XPATH,
            "//input[@value='Log In'][@type='submit']",
            cancellation_token=cancellation_token,
        )
        login_button.click()


class BoxCastClientFactory:
    def __init__(
        self,
        messenger: Messenger,
        credential_store: CredentialStore,
        cancellation_token: Optional[CancellationToken],
        headless: bool = True,
        lazy_login: bool = False,
        log_directory: Optional[Path] = None,
        log_file_name: Optional[str] = None,
    ):
        self._messenger = messenger
        self._credential_store = credential_store
        self._headless = headless
        self._log_directory = log_directory
        self._log_file_name = log_file_name if log_file_name else "boxcast_client"
        if self._log_file_name.endswith(".log"):
            self._log_file_name = self._log_file_name[:-4]

        if not lazy_login:
            self._test_login(cancellation_token)

    def get_client(self, cancellation_token: Optional[CancellationToken]):
        if not self._log_directory:
            log_file = None
        else:
            date_ymd = datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.now().strftime("%H-%M-%S")
            log_file = self._log_directory.joinpath(
                f"{date_ymd} {current_time} {self._log_file_name}.log"
            )
        return BoxCastClient(
            messenger=self._messenger,
            credential_store=self._credential_store,
            headless=self._headless,
            log_file=log_file,
            cancellation_token=cancellation_token,
        )

    def _test_login(self, cancellation_token: Optional[CancellationToken]):
        # Get a page other than the landing page just to be sure that we're logged in
        with self.get_client(cancellation_token) as test_client:
            test_client.get(
                "https://dashboard.boxcast.com/schedule",
                cancellation_token=cancellation_token,
            )


def export_to_vimeo(
    client: BoxCastClient,
    event_url: str,
    cancellation_token: CancellationToken,
):
    client.get(event_url, cancellation_token)

    download_or_export_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Download or Export Recording')]",
        cancellation_token=cancellation_token,
        timeout=timedelta(minutes=60),
    )
    download_or_export_button.click()

    vimeo_tab = client.wait_for_single_element(
        By.XPATH,
        "//div[@id='headlessui-portal-root']//a[contains(., 'Vimeo')]",
        cancellation_token=cancellation_token,
    )
    vimeo_tab.click()

    user_dropdown_label = client.wait_for_single_element(
        By.XPATH,
        "//label[contains(., 'Export as User')]",
        cancellation_token=cancellation_token,
    )
    user_dropdown_id = _get_attribute(user_dropdown_label, "for")

    user_dropdown = client.wait_for_single_element(
        By.XPATH,
        f"//select[@id='{user_dropdown_id}']",
        cancellation_token=cancellation_token,
    )
    user_dropdown_select = Select(user_dropdown)
    user_dropdown_select.select_by_visible_text("River's Edge")  # type: ignore

    vimeo_export_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Export To Vimeo')]",
        cancellation_token=cancellation_token,
    )
    vimeo_export_button.click()


def download_captions(
    client: BoxCastClient,
    captions_tab_url: str,
    download_path: Path,
    destination_path: Path,
    cancellation_token: CancellationToken,
):
    client.get(captions_tab_url, cancellation_token)
    download_captions_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Download Captions')]",
        cancellation_token=cancellation_token,
        timeout=timedelta(minutes=60),
    )
    download_captions_button.click()
    vtt_download_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'WebVTT File (.vtt)')]",
        cancellation_token=cancellation_token,
        timeout=timedelta(seconds=1),
    )
    vtt_download_button.click()

    _wait_for_file_to_exist(
        download_path,
        timeout=timedelta(seconds=60),
        cancellation_token=cancellation_token,
    )
    if not destination_path.parent.exists():
        destination_path.parent.mkdir(exist_ok=True, parents=True)
    shutil.move(download_path, destination_path)


def upload_captions_to_boxcast(
    client: BoxCastClient,
    url: str,
    file_path: Path,
    cancellation_token: CancellationToken,
):
    client.get(url, cancellation_token)

    # There is also a settings "button" in the sidebar, but it is represented
    # with an <a> tag rather than a <button> tag. Just in case, check that the
    # button selected here is not in the sidebar.
    settings_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Settings')][not(ancestor::nav)]",
        cancellation_token=cancellation_token,
        timeout=timedelta(seconds=10),
    )
    settings_button.click()

    replace_captions_option = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Replace Captions with WebVTT File')]",
        cancellation_token=cancellation_token,
    )
    replace_captions_option.click()

    file_input = client.wait_for_single_element(
        By.XPATH,
        "//input[@type='file'][contains(@accept, '.vtt')]",
        cancellation_token=cancellation_token,
        clickable=False,
    )
    # Don't send file_path.as_posix(), otherwise BoxCast won't find the file
    # for some reason
    _send_keys(file_input, str(file_path))

    submit_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Save Uploaded Caption File')]",
        cancellation_token=cancellation_token,
        timeout=timedelta(seconds=10),
    )
    submit_button.click()


def create_rebroadcast(
    rebroadcast_setup_url: str,
    source_broadcast_title: str,
    rebroadcast_title: str,
    start_datetime: datetime,
    client: BoxCastClient,
    messenger: Messenger,
    cancellation_token: CancellationToken,
):
    _get_rebroadcast_page(
        rebroadcast_setup_url,
        source_broadcast_title,
        client,
        messenger,
        cancellation_token,
    )

    _set_event_name(rebroadcast_title, client, cancellation_token)

    # TODO: Check other things like event date, description, etc?
    # I don't see a way to set the value of the date input once I located it.
    # clear() and send_keys() just bring up the graphical date picker :(

    _set_event_start_time(start_datetime, client, cancellation_token)

    try:
        _make_event_not_recorded(client, cancellation_token)
    except Exception as e:
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Failed to make rebroadcast not recorded: {e}",
            stacktrace=traceback.format_exc(),
        )

    _press_schedule_broadcast_button(client, cancellation_token)

    # The website should redirect to the page for the newly-created rebroadcast after the button is pressed
    expected_prefix = "https://dashboard.boxcast.com/broadcasts"
    redirect_timeout = 10
    client.wait(
        condition=lambda driver: driver.current_url.startswith(expected_prefix),
        timeout=timedelta(seconds=10),
        message=f"Did not get redirected to the expected page (starting with {expected_prefix}) within {redirect_timeout} seconds.",
        cancellation_token=cancellation_token,
    )


def _wait_for_file_to_exist(
    path: Path, timeout: timedelta, cancellation_token: CancellationToken
):
    wait_start = datetime.now()
    while True:
        cancellation_token.raise_if_cancelled()
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
    cancellation_token: CancellationToken,
):
    """
    Get the rebroadcast page and wait until the source broadcast is available.
    """
    retry_seconds = 60
    max_retries = 60
    for _ in range(max_retries):
        client.get(rebroadcast_setup_url, cancellation_token)
        # Give the page a moment to load
        sleep_attentively(timedelta(seconds=5), cancellation_token=cancellation_token)
        by = By.XPATH
        value = f"//a[contains(., '{expected_source_name}')]"
        elements = client.find_elements(by, value)
        if not elements:
            messenger.log_status(
                TaskStatus.RUNNING,
                f"The source broadcast is not yet available as of {datetime.now().strftime('%H:%M:%S')}. Retrying in {retry_seconds} seconds.",
            )
            autochecklist.sleep_attentively(
                timedelta(seconds=retry_seconds), cancellation_token
            )
        elif len(elements) == 1:
            messenger.log_status(
                TaskStatus.RUNNING,
                "Rebroadcast page loaded: source broadcast is as expected.",
            )
            return
        else:
            raise ValueError(
                f"{len(elements)} elements matched the given criteria (by = {by}, value = '{value}')."
            )
    raise ValueError(
        f"The rebroadcast setup page did not load within {max_retries} attempts."
    )


def _set_event_name(
    name: str, client: BoxCastClient, cancellation_token: CancellationToken
):
    name_label = client.wait_for_single_element(
        By.XPATH,
        "//label[contains(., 'Broadcast Name')]",
        cancellation_token=cancellation_token,
    )
    name_input = client.wait_for_single_element(
        By.ID,
        _get_attribute(name_label, "for"),
        cancellation_token=cancellation_token,
    )
    name_input.clear()
    _send_keys(name_input, name)


def _set_event_start_time(
    start_datetime: datetime,
    client: BoxCastClient,
    cancellation_token: CancellationToken,
):
    time_12h = start_datetime.strftime("%I:%M %p")
    # BoxCast removes leading 0, so we need to as well when comparing the
    # expected and actual values
    if time_12h.startswith("0"):
        time_12h = time_12h[1:]

    start_time_input = client.wait_for_single_element(
        By.XPATH,
        "//div[@id='schedule-date-time-starts-at']//input",
        cancellation_token=cancellation_token,
    )
    # Time should normally not be longer than 8 characters, but use large
    # safety margin because hitting backspace should be quick
    for _ in range(100):
        if not _get_attribute(start_time_input, "value"):
            break
        _send_keys(start_time_input, Keys.BACKSPACE)
    if _get_attribute(start_time_input, "value"):
        raise ValueError("Failed to clear the start time input.")
    _send_keys(start_time_input, time_12h)
    # Move focus away from the input element and then check that the value was
    # accepted and not ignored
    _send_keys(start_time_input, Keys.TAB)
    actual_value = _get_attribute(start_time_input, "value")
    if actual_value != time_12h:
        raise ValueError(
            f"Failed to set time: tried to write '{time_12h}' but the input's actual value is '{actual_value}'."
        )


def _make_event_not_recorded(
    client: BoxCastClient, cancellation_token: CancellationToken
):
    recording_options_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Recording Options')]",
        cancellation_token=cancellation_token,
    )
    recording_options_button.click()
    record_broadcast_label = client.wait_for_single_element(
        By.XPATH,
        "//label[contains(., 'Record Broadcast')]",
        cancellation_token=cancellation_token,
    )
    record_broadcast_checkbox = client.wait_for_single_element(
        By.ID,
        _get_attribute(record_broadcast_label, "for"),
        cancellation_token=cancellation_token,
    )
    if _get_attribute(record_broadcast_checkbox, "checked") == "true":
        record_broadcast_checkbox.click()


def _press_schedule_broadcast_button(
    client: BoxCastClient, cancellation_token: CancellationToken
):
    submit_button = client.wait_for_single_element(
        By.XPATH,
        "//button[contains(., 'Schedule Broadcast')]",
        cancellation_token=cancellation_token,
    )
    submit_button.click()


def _get_attribute(element: WebElement, name: str) -> str:
    # Use this helper to avoid having to turn off Pyright everywhere
    return element.get_attribute(name)  # type: ignore


def _send_keys(element: WebElement, keys: str):
    # Use this helper to avoid having to turn off Pyright everywhere
    element.send_keys(keys)  # type: ignore
