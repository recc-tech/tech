import os
import unittest
from datetime import date, datetime, timedelta, timezone

import external_services
from args import ReccArgs
from config import Config
from external_services import IssueType
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.webdriver import WebDriver


class GitHubTestCase(unittest.TestCase):
    def test_find_foh_video_setup_checklist(self) -> None:
        # This will fail if run very early on Sunday, but that's not usually
        # when we're running tests anyway
        sunday = _get_latest_sunday()
        expected_title = f"FOH Video Setup (Sunday, {sunday.strftime('%B')} {_day_with_suffix(sunday.day)})"
        issue = external_services.find_latest_github_issue(
            type=IssueType.FOH_VIDEO_SETUP, config=_get_config()
        )
        self.assertEqual(expected_title, issue.title)
        self._check_web_page(url=issue.html_url, expected_title=expected_title)

    def test_find_mcr_video_setup_checklist(self) -> None:
        # This will fail if run very early on Sunday, but that's not usually
        # when we're running tests anyway
        sunday = _get_latest_sunday()
        expected_title = f"MCR Video Setup (Sunday, {sunday.strftime('%B')} {_day_with_suffix(sunday.day)})"
        issue = external_services.find_latest_github_issue(
            type=IssueType.MCR_VIDEO_SETUP, config=_get_config()
        )
        self.assertEqual(expected_title, issue.title)
        self._check_web_page(url=issue.html_url, expected_title=expected_title)

    def test_find_mcr_video_teardown_checklist(self) -> None:
        # This will fail if run very early on Sunday, but that's not usually
        # when we're running tests anyway
        sunday = _get_latest_sunday()
        expected_title = f"MCR Video Teardown (Sunday, {sunday.strftime('%B')} {_day_with_suffix(sunday.day)})"
        issue = external_services.find_latest_github_issue(
            type=IssueType.MCR_VIDEO_TEARDOWN, config=_get_config()
        )
        self.assertEqual(expected_title, issue.title)
        self._check_web_page(url=issue.html_url, expected_title=expected_title)

    def test_check_web_page_wrong_title(self) -> None:
        """
        Test that the _check_web_page() method indeed fails if the title is
        wrong.
        """
        with self.assertRaises(AssertionError):
            self._check_web_page(
                # This URL actually goes to the issue from August 11
                url="https://github.com/recc-tech/tech/issues/399",
                expected_title="FOH Video Setup (Sunday, August 4th)",
            )

    def test_check_web_page_wrong_url(self) -> None:
        """
        Test that the _check_web_page() method indeed fails if the URL points
        to something other than the issue page.
        """
        with self.assertRaises(NoSuchElementException):
            self._check_web_page(
                url="https://api.github.com/repos/recc-tech/tech/issues/399",
                expected_title="FOH Video Setup (Sunday, August 11th)",
            )

    def _check_web_page(self, url: str, expected_title: str) -> None:
        service = Service(log_path=os.devnull)
        options = Options()
        options.add_argument("-headless")
        with WebDriver(service=service, options=options) as driver:
            driver.get(url)
            elems = driver.find_elements(
                By.XPATH, "//h1[not(ancestor::div[@id='discussion_bucket'])]/bdi"
            )
            visible_elems = [e for e in elems if e.is_displayed()]
            if len(visible_elems) == 0:
                raise NoSuchElementException(
                    f"Found {len(visible_elems)} visible h1 elements."
                )
            if len(visible_elems) != 1:
                raise ValueError(f"Found {len(visible_elems)} visible h1 elements.")
            h1 = visible_elems[0]
            self.assertEqual(expected_title, h1.get_attribute("textContent"))


def _get_config() -> Config:
    return Config(ReccArgs.parse([]), allow_multiple_only_for_testing=True)


def _get_latest_sunday() -> date:
    now = datetime.now(timezone.utc)
    today = now.date()
    day = today
    SUNDAY = 7
    while day.isoweekday() != SUNDAY:
        day -= timedelta(days=1)
    # The issues are only created at around 9:15 UTC on Sundays (see the GitHub
    # Actions workflow).
    # If these tests are run on a Sunday before 9:15, the latest issues will be
    # from last week, not today.
    if day == today and now.hour < 9:
        day -= timedelta(days=7)
    return day


def _day_with_suffix(day: int) -> str:
    if day // 10 == 1:
        # 10th, 11th, 12th, 13th, 14th, 15th, 16th, 17th, 18th, 19th
        return f"{day}th"
    elif day % 10 == 1:
        # 1st, 21st, 31st
        return f"{day}st"
    elif day % 10 == 2:
        # 2nd, 22nd
        return f"{day}nd"
    elif day % 10 == 3:
        # 3rd, 23rd
        return f"{day}rd"
    else:
        #        4th,  5th,  6th,  7th,  8th,  9th
        # 20th, 24th, 25th, 26th, 27th, 28th, 29th, 30th
        return f"{day}th"
