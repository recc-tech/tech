import inspect
import os
import unittest
from pathlib import Path
from tkinter import Tk

from lib import load_plan_summary, plan_summary_to_html
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.webdriver import WebDriver

_DATA_DIR = Path(__file__).parent.joinpath("summarize_plan_data")
_TEMP_DIR = Path(__file__).parent.joinpath("summarize_plan_temp")


class PlanSummaryHtmlTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def test_copy(self) -> None:
        summary = load_plan_summary(_DATA_DIR.joinpath("20240414_summary.json"))
        summary_html = plan_summary_to_html(summary)
        f = _TEMP_DIR.joinpath("summary.html")
        f.write_text(summary_html, encoding="utf-8")

        # NOTE: Copying doesn't work in headless mode for some reason
        service = Service(log_path=os.devnull)
        driver = WebDriver(service=service)
        try:
            driver.get(f.resolve().as_uri())
            Alert(driver).accept()
            btn = driver.find_element(By.XPATH, "//button[contains(., 'Copy')]")
            btn.click()
        finally:
            driver.quit()

        expected_text = inspect.cleandoc(
            """Worthy Of The Feast
            Matthew 22:1-14 NLT
            Our Worth Isn’t Earned It’s Given
            Matthew 22:4
            Our Worth Is Experienced Through Acceptance
            Matthew 22:10
            Our Worth Is Revealed By Our Garments
            Matthew 22:11
            You Are Worthy Because You Are Chosen
            Matthew 22:14
            Our Worth Is Connected To Our Embrace Of The Worth Of The Feast
            Live According To The Level Of Worth We Have Received"""
        )
        self.assertEqual(expected_text, _get_clipboard_text())


def _get_clipboard_text() -> str:
    root = Tk()
    x = root.clipboard_get()
    root.quit()
    return x
