# pyright: reportUnnecessaryTypeIgnoreComment=information
# This is needed so platform-specific code (subprocess.CREATE_NO_WINDOW) can type-check
from __future__ import annotations

import os
import platform
import subprocess
import time
import traceback
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional, Tuple, Type, TypeVar

from autochecklist import CancellationToken, Messenger, ProblemLevel
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC

T = TypeVar("T")


class ReccWebDriver(WebDriver):
    MAX_STARTUP_ATTEMPTS = 3

    def __new__(
        cls,
        messenger: Messenger,
        headless: bool = True,
        log_file: Optional[Path] = None,
    ):
        # Selenium sometimes raises
        # "selenium.common.exceptions.WebDriverException: Message: Process
        # unexpectedly closed with status 0" on startup!
        # The issue seems to happen specifically in super().__init__(...), not
        # in super().__new__(), so the try ... except must include that line.
        # I'm not sure it's safe to call super().__init__(...) multiple times
        # on the same object, so I'd rather construct a new instance from
        # scratch.
        # But if I move that to a new() classmethod, subclasses whose
        # constructors take different arguments will need to override those
        # methods in an incompatible manner.
        # Furthermore, a new() classmethod is awkward because clients might
        # forget about it and use the constructor directly.
        attempts = 0
        while True:
            try:
                driver = super().__new__(cls)
                driver.__initialize(headless=headless, log_file=log_file)
                return driver
            except WebDriverException as e:
                attempts += 1
                if attempts >= cls.MAX_STARTUP_ATTEMPTS:
                    raise
                else:
                    messenger.log_problem(
                        ProblemLevel.WARN,
                        f"Failed to create Selenium web driver instance: {e}",
                        traceback.format_exc(),
                    )

    def __init__(
        self,
        messenger: Messenger,
        headless: bool = True,
        log_file: Optional[Path] = None,
    ):
        pass

    def __initialize(self, headless: bool, log_file: Optional[Path]):
        options = Options()
        if headless:
            options.add_argument("-headless")
        if platform.system() == "Windows":
            # Hide the geckodriver terminal
            creation_flags = (
                subprocess.CREATE_NO_WINDOW  # pyright: ignore [reportAttributeAccessIssue]
            )
        else:
            # subprocess.CREATE_NO_WINDOW is only available on Windows
            creation_flags = 0
        service = Service(
            log_path=log_file.as_posix() if log_file else os.devnull,
            popen_kw={"creation_flags": creation_flags},
        )
        super().__init__(options=options, service=service)

    def wait(
        self,
        condition: Callable[[ReccWebDriver], T],
        timeout: timedelta,
        message: str,
        cancellation_token: Optional[CancellationToken],
        poll_frequency: timedelta = timedelta(seconds=0.5),
        ignore_exceptions: Optional[Tuple[Type[BaseException], ...]] = None,
    ) -> T:
        if ignore_exceptions is None:
            ignore_exceptions = tuple()
        start = time.monotonic()
        timeout_seconds = timeout.total_seconds()
        poll_frequency_seconds = poll_frequency.total_seconds()
        while True:
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            try:
                value = condition(self)
                if value:
                    return value
            except ignore_exceptions:
                pass
            time.sleep(poll_frequency_seconds)
            if time.monotonic() - start > timeout_seconds:
                raise TimeoutException(message)

    def wait_for_single_element(
        self,
        by: str,
        value: str,
        cancellation_token: Optional[CancellationToken],
        # Whether the element needs to be clickable
        clickable: bool = True,
        # This seems like a reasonably safe amount of time to wait if you expect the element to already be loaded,
        # but potentially be obscured by another element (e.g., a dropdown menu)
        timeout: timedelta = timedelta(seconds=5),
    ) -> WebElement:
        ec = (
            EC.element_to_be_clickable((by, value))
            if clickable
            else EC.presence_of_element_located((by, value))
        )

        try:
            self.wait(
                condition=ec,
                timeout=timeout,
                message="",
                cancellation_token=cancellation_token,
                ignore_exceptions=(NoSuchElementException,),
            )
        except TimeoutException:
            # The error might be because there are no matches, but it could also be because there are multiple matches and the first one isn't clickable!
            elements = self.find_elements(by, value)
            if len(elements) == 0:
                raise NoSuchElementException(
                    f"No element found for the given criteria (by = {by}, value = '{value}')."
                ) from None
            elif len(elements) == 1:
                raise ValueError(
                    f"An element was found for the given criteria (by = {by}, value = '{value}'), but it does not seem to be clickable."
                ) from None
            else:
                raise ValueError(
                    f"{len(elements)} elements matched the given criteria (by = {by}, value = '{value}')."
                ) from None

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
