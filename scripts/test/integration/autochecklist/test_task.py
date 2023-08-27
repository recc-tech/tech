import test.integration.autochecklist.example_tasks as example_functions
import unittest
from pathlib import Path
from test.integration.autochecklist.example_tasks import MyList, TestConfig
from unittest.mock import ANY, call, create_autospec

from autochecklist.messenger import Messenger, ProblemLevel
from autochecklist.task import FunctionFinder, TaskGraph, TaskModel


class TaskGraphTestCase(unittest.TestCase):
    def test_task_graph(self):
        my_list = MyList()

        def append_wait(*_: object):
            my_list.the_list.append("wait")

        messenger = create_autospec(Messenger)
        # Have wait() append to the list so that we can check when it was
        # called
        messenger.wait.side_effect = append_wait
        messenger.shutdown_requested = False
        config = TestConfig()
        function_finder = FunctionFinder(
            module=example_functions, arguments=[my_list, config], messenger=messenger
        )

        json_file = Path(__file__).parent.joinpath("example_tasks.json")
        model = TaskModel.load(json_file)
        graph = TaskGraph(
            model, messenger=messenger, function_finder=function_finder, config=config
        )
        graph.run()

        self.assertIn(
            my_list.the_list,
            [
                [TestConfig.FOO, "wait", "wait", TestConfig.BAZ, TestConfig.QUX],
                [TestConfig.FOO, "wait", "wait", TestConfig.QUX, TestConfig.BAZ],
            ],
        )
        messenger.wait.assert_has_calls(
            [
                call(prompt=f"Add the value '{TestConfig.BAR}' to the list 🙂."),
                call(prompt=f"This task will raise an error."),
            ],
            any_order=False,
        )
        messenger.log_problem.assert_called_once_with(
            level=ProblemLevel.ERROR,
            message="An error occurred while trying to complete the task automatically: This is an error raised by a task implementation.",
            stacktrace=ANY,
        )