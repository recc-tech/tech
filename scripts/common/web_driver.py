from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional, Tuple, Type, TypeVar

from autochecklist import CancellationToken
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC

T = TypeVar("T")


class ReccWebDriver(WebDriver):
    def __init__(self, headless: bool = True, log_file: Optional[Path] = None):
        options = Options()
        if headless:
            options.add_argument("-headless")  # type: ignore
        service = (
            Service(log_path=log_file.as_posix())
            if log_file
            else Service(log_path="NUL")
        )
        # TODO: This raises "selenium.common.exceptions.WebDriverException: Message: Process unexpectedly closed with status 0,"
        # but only at church and only the first time!
        super().__init__(options=options, service=service)  # type: ignore

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
        ec = EC.element_to_be_clickable((by, value)) if clickable else EC.presence_of_element_located((by, value))  # type: ignore

        try:
            self.wait(
                condition=ec,  # type: ignore
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
