import unittest
from datetime import date

import external_services
from args import ReccArgs
from config import Config
from external_services import Issue, IssueType


class GitHubTestCase(unittest.TestCase):
    def test_find_foh_setup_checklist_20240811(self) -> None:
        expected = Issue(html_url="https://github.com/recc-tech/tech/issues/399")
        actual = external_services.find_github_issue(
            type=IssueType.FOH_SETUP,
            dt=date(year=2024, month=8, day=11),
            config=self._get_config(),
        )
        self.assertEqual(expected, actual)

    def test_find_foh_setup_checklist_20240813(self) -> None:
        expected = Issue(html_url="https://github.com/recc-tech/tech/issues/405")
        actual = external_services.find_github_issue(
            type=IssueType.FOH_SETUP,
            dt=date(year=2024, month=8, day=13),
            config=self._get_config(),
        )
        self.assertEqual(expected, actual)

    def test_find_mcr_setup_checklist_20240811(self) -> None:
        expected = Issue(html_url="https://github.com/recc-tech/tech/issues/398")
        actual = external_services.find_github_issue(
            type=IssueType.MCR_SETUP,
            dt=date(year=2024, month=8, day=11),
            config=self._get_config(),
        )
        self.assertEqual(expected, actual)

    def test_find_mcr_setup_checklist_20240813(self) -> None:
        expected = Issue(html_url="https://github.com/recc-tech/tech/issues/406")
        actual = external_services.find_github_issue(
            type=IssueType.MCR_SETUP,
            dt=date(year=2024, month=8, day=13),
            config=self._get_config(),
        )
        self.assertEqual(expected, actual)

    def test_find_mcr_teardown_checklist_20240811(self) -> None:
        expected = Issue(html_url="https://github.com/recc-tech/tech/issues/400")
        actual = external_services.find_github_issue(
            type=IssueType.MCR_TEARDOWN,
            dt=date(year=2024, month=8, day=11),
            config=self._get_config(),
        )
        self.assertEqual(expected, actual)

    def test_find_mcr_teardown_checklist_20240813(self) -> None:
        expected = Issue(html_url="https://github.com/recc-tech/tech/issues/407")
        actual = external_services.find_github_issue(
            type=IssueType.MCR_TEARDOWN,
            dt=date(year=2024, month=8, day=13),
            config=self._get_config(),
        )
        self.assertEqual(expected, actual)

    def _get_config(self) -> Config:
        return Config(ReccArgs.parse([]), allow_multiple_only_for_testing=True)
