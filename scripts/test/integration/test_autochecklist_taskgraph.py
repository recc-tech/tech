import unittest
from pathlib import Path
from unittest.mock import ANY, call, create_autospec

from autochecklist import (
    FunctionFinder,
    Messenger,
    ProblemLevel,
    TaskGraph,
    TaskModel,
    UserResponse,
)

from .autochecklist_data import example_tasks
from .autochecklist_data.example_tasks import MyList, TestConfig


class TaskGraphTestCase(unittest.TestCase):
    def test_task_graph(self):
        my_list = MyList()

        def append_wait(*_args: object, **_kwargs: object):
            my_list.the_list.append("wait")
            return UserResponse.DONE

        messenger = create_autospec(Messenger)
        # Have wait() append to the list so that we can check when it was
        # called
        messenger.wait.side_effect = append_wait
        messenger.is_closed = False
        config = TestConfig(ui="tk", verbose=False, no_run=False, auto_tasks=None)
        function_finder = FunctionFinder(
            module=example_tasks, arguments=[my_list, config], messenger=messenger
        )

        json_file = Path(__file__).parent.joinpath(
            "autochecklist_data", "example_tasks.json"
        )
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
                call(
                    prompt=f"Add the value '{TestConfig.BAR}' to the list 🙂.",
                    allowed_responses={UserResponse.SKIP, UserResponse.DONE},
                ),
                call(
                    prompt=f"This task will raise an error.",
                    allowed_responses={UserResponse.SKIP, UserResponse.RETRY},
                ),
            ],
            any_order=False,
        )
        messenger.log_problem.assert_called_once_with(
            level=ProblemLevel.ERROR,
            message="An error occurred while trying to complete the task automatically: This is an error raised by a task implementation.",
            stacktrace=ANY,
        )
