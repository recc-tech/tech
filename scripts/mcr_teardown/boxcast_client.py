from autochecklist.credentials import get_credential
from autochecklist.messenger import LogLevel, Messenger
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait

_LOGIN_URL = "https://login.boxcast.com/login"
_USERNAME = "lorenzo@riversedge.life"


class BoxCastClient(WebDriver):
    _TASK_NAME = "BOXCAST CLIENT"

    def __init__(self, messenger: Messenger, headless: bool = True):
        options = Options()
        if headless:
            options.add_argument("-headless")  # type: ignore
        super().__init__(options=options)  # type: ignore
        self._messenger = messenger

    def get(self, url: str):
        super().get(url)
        wait = WebDriverWait(self, timeout=10)
        wait.until(lambda driver: driver.current_url in [url, _LOGIN_URL])  # type: ignore

        if self.current_url == _LOGIN_URL:
            self._login()
            wait.until(lambda driver: driver.current_url == url)  # type: ignore

    def _login(self):
        first_attempt = True
        while True:
            email_textbox = self.find_single_element(By.ID, "email")
            email_textbox.send_keys(_USERNAME)  # type: ignore

            password_textbox = self.find_single_element(By.ID, "password")
            password = get_credential(
                "boxcast_password",
                "BoxCast password",
                not first_attempt,
                self._messenger,
            )
            password_textbox.send_keys(password)  # type: ignore

            login_button = self.find_single_element(
                By.XPATH, "//input[@value='Log In'][@type='submit']"
            )
            login_button.click()

            wait = WebDriverWait(self, timeout=5)
            try:
                wait.until(lambda driver: driver.current_url != _LOGIN_URL)  # type: ignore
                self._messenger.log(
                    self._TASK_NAME, LogLevel.DEBUG, "Successfully logged into BoxCast."
                )
                return
            except TimeoutException:
                first_attempt = False
                self._messenger.log(
                    self._TASK_NAME, LogLevel.ERROR, "Failed to log into BoxCast."
                )

    def find_single_element(self, by: str, value: str) -> WebElement:
        elements = self.find_elements(by, value)
        if len(elements) == 0:
            raise NoSuchElementException(
                f"No element found for the given criteria (by = {by}, value = '{value}')"
            )
        elif len(elements) == 1:
            return elements[0]
        else:
            raise ValueError(
                f"Expected to find one matching element, but found {len(elements)}."
            )


class BoxCastClientFactory:
    def __init__(self, messenger: Messenger, headless: bool):
        self._messenger = messenger
        self._headless = headless

    def get_client(self):
        return BoxCastClient(messenger=self._messenger, headless=self._headless)