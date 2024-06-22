import unittest
import warnings
from pathlib import Path

import autochecklist.messenger.tk.responsive_textbox as tb
import requests
from autochecklist import TaskModel

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.joinpath("config")
_MCR_SETUP_TASKS = _CONFIG_DIR.joinpath("mcr_setup_tasks.json")
_MCR_TEARDOWN_TASKS = _CONFIG_DIR.joinpath("mcr_teardown_tasks.json")


class ParseTaskDescriptionsTestCase(unittest.TestCase):
    """
    Check that the MCR setup and teardown tasks that have formatted text
    (e.g., "[[url|https://example.com]]") can be parsed.
    """

    @classmethod
    def setUpClass(cls) -> None:
        warnings.simplefilter("error")

    def setUp(self) -> None:
        # Make sure at least one URL was checked (i.e., I didn't forget to
        # check or somehow skip them all)
        self._num_urls = 0

    def test_load_mcr_setup_tasks(self) -> None:
        model = TaskModel.load(_MCR_SETUP_TASKS)
        self._check_model(model)
        self.assertGreaterEqual(self._num_urls, 1)

    def test_load_mcr_teardown_tasks(self) -> None:
        model = TaskModel.load(_MCR_TEARDOWN_TASKS)
        self._check_model(model)
        self.assertGreaterEqual(self._num_urls, 1)

    def test_check_url(self) -> None:
        """
        Make sure the test for invalid URLs would actually catch problems.
        Unfortunately, I'm not sure how to catch cases where the main URL is
        valid but the *anchor* part is broken (e.g., https://github.com/recc-tech/tech/wiki/MCR-Visuals-Troubleshooting#missing).
        """
        url = "https://github.com/recc-tech/tech/wiki/Missing"
        with self.assertRaises(ValueError) as cm:
            self._check_url(url)
        self.assertEqual(f"The link {url} appears to be dead.", str(cm.exception))

    def _check_model(self, model: TaskModel) -> None:
        if model.description:
            chunks = tb.parse(model.description)
            for c in chunks:
                match c:
                    case tb.UrlText(_, url):
                        self._check_url(url)
                    case _:
                        pass
        for st in model.subtasks:
            self._check_model(st)

    def _check_url(self, url: str) -> None:
        response = requests.head(url)
        if response.status_code != 200:
            raise ValueError(f"The link {url} appears to be dead.")
        self._num_urls += 1
