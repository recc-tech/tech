import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class ReccWebDriver(WebDriver):
    def __init__(self, headless: bool = True):
        options = Options()
        if headless:
            options.add_argument("-headless")  # type: ignore
        super().__init__(options=options)  # type: ignore

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
