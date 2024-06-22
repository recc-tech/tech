import unittest
import warnings
from pathlib import Path

import autochecklist.messenger.tk.responsive_textbox as tb
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

    def test_load_mcr_setup_tasks(self) -> None:
        model = TaskModel.load(_MCR_SETUP_TASKS)
        self._check_model(model)

    def test_load_mcr_teardown_tasks(self) -> None:
        model = TaskModel.load(_MCR_TEARDOWN_TASKS)
        self._check_model(model)

    def _check_model(self, model: TaskModel) -> None:
        if model.description:
            tb.parse(model.description)
        for st in model.subtasks:
            self._check_model(st)
