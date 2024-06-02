import sys
import unittest
from pathlib import Path
from test.mock import FixedDependencyProvider, MockMessenger
from typing import List, Optional, Tuple

import autochecklist
from autochecklist import (
    BaseArgs,
    BaseConfig,
    Messenger,
    ProblemLevel,
    TaskModel,
    TaskStatus,
)

_DATA_DIR = Path(__file__).parent.joinpath("autochecklist_data")


def A(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running A")


def B(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running B")


def C(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running C")


def D(msg: Messenger) -> None:
    # TODO: Make this one fail the first time
    msg.log_status(TaskStatus.RUNNING, "Running D")


def E(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running E")


class TaskGraphTestCase(unittest.TestCase):
    def test_script_from_file(self) -> None:
        msg = MockMessenger(log_file=_DATA_DIR.joinpath("run_from_file.log"))
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[])
        tasks = _DATA_DIR.joinpath("tasks.json")
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=sys.modules[__name__],
        )
        self._check_status_trace(msg.mock_input_messenger.statuses, p=tasks)
        self.assertEqual([], msg.mock_input_messenger.errors)

    # TODO: Make some of the tasks manual? Have some of them fail at first but
    # work on repeat attempts?
    def test_script_from_model(self) -> None:
        msg = MockMessenger(log_file=_DATA_DIR.joinpath("run_from_model.log"))
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[])
        tasks = TaskModel(
            name="script_from_model",
            subtasks=[
                TaskModel(name="A", description="Task A"),
                TaskModel(name="B", description="Task B", prerequisites={"A"}),
                TaskModel(name="C", description="Task C", prerequisites={"A"}),
                TaskModel(name="D", description="Task D", prerequisites={"B", "C"}),
                TaskModel(name="E", description="Task E", prerequisites={"D"}),
            ],
        )
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=sys.modules[__name__],
        )
        self._check_status_trace(msg.mock_input_messenger.statuses, p=None)
        self.assertEqual([], msg.mock_input_messenger.errors)

    def test_script_with_error(self) -> None:
        msg = MockMessenger(log_file=_DATA_DIR.joinpath("run_from_model.log"))
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[])
        tasks = TaskModel(
            name="script_from_model",
            subtasks=[
                TaskModel(name="A", description="Task A"),
                TaskModel(name="B", description="Task B", prerequisites={"fake"}),
            ],
        )
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=sys.modules[__name__],
        )
        expected_status_trace = [
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Loading tasks."),
            ("SCRIPT MAIN", TaskStatus.DONE, "Script failed."),
            ("dependency_provider", TaskStatus.RUNNING, "Shut down."),
        ]
        self.assertEqual(expected_status_trace, msg.mock_input_messenger.statuses)
        expected_error_trace = [
            (
                "SCRIPT MAIN",
                ProblemLevel.FATAL,
                "Failed to load the task graph: The prerequisite 'fake' could not be found.",
            )
        ]
        self.assertEqual(expected_error_trace, msg.mock_input_messenger.errors)

    def _check_status_trace(
        self, status_trace: List[Tuple[str, TaskStatus, str]], p: Optional[Path]
    ) -> None:
        load_msg = (
            "Loading tasks."
            if p is None
            else f"Loading tasks from {p.resolve().as_posix()}."
        )
        expected_start_trace = [
            ("SCRIPT MAIN", TaskStatus.RUNNING, load_msg),
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Running tasks."),
            ("A", TaskStatus.NOT_STARTED, "-"),
            ("B", TaskStatus.NOT_STARTED, "-"),
            ("C", TaskStatus.NOT_STARTED, "-"),
            ("D", TaskStatus.NOT_STARTED, "-"),
            ("E", TaskStatus.NOT_STARTED, "-"),
            ("A", TaskStatus.RUNNING, "Task started."),
            ("A", TaskStatus.RUNNING, "Running A"),
            ("A", TaskStatus.DONE, "Task completed automatically."),
        ]
        n_start = len(expected_start_trace)
        expected_trace_b = [
            ("B", TaskStatus.RUNNING, "Task started."),
            ("B", TaskStatus.RUNNING, "Running B"),
            ("B", TaskStatus.DONE, "Task completed automatically."),
        ]
        expected_trace_c = [
            ("C", TaskStatus.RUNNING, "Task started."),
            ("C", TaskStatus.RUNNING, "Running C"),
            ("C", TaskStatus.DONE, "Task completed automatically."),
        ]
        n_mid = len(expected_trace_b) + len(expected_trace_c)
        expected_end_trace = [
            ("D", TaskStatus.RUNNING, "Task started."),
            ("D", TaskStatus.RUNNING, "Running D"),
            ("D", TaskStatus.DONE, "Task completed automatically."),
            ("E", TaskStatus.RUNNING, "Task started."),
            ("E", TaskStatus.RUNNING, "Running E"),
            ("E", TaskStatus.DONE, "Task completed automatically."),
            ("SCRIPT MAIN", TaskStatus.DONE, "All done!"),
            ("dependency_provider", TaskStatus.RUNNING, "Shut down."),
        ]
        # Exactly one right order for start and end
        self.assertEqual(expected_start_trace, status_trace[:n_start])
        self.assertEqual(expected_end_trace, status_trace[(n_start + n_mid) :])
        # Order of B and C doesn't matter
        actual_trace_b = [
            x for x in status_trace[n_start : (n_start + n_mid)] if x[0] == "B"
        ]
        actual_trace_c = [
            x for x in status_trace[n_start : (n_start + n_mid)] if x[0] == "C"
        ]
        self.assertEqual(expected_trace_b, actual_trace_b)
        self.assertEqual(expected_trace_c, actual_trace_c)
