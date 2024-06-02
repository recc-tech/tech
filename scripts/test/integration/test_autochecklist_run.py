import test.integration.autochecklist_data.abcde as abcde
import test.integration.autochecklist_data.cancel as cancel
import test.integration.autochecklist_data.fail_then_succeed as fail_then_succeed
import test.integration.autochecklist_data.keyboard_interrupt as keyboard_interrupt
import unittest
from pathlib import Path
from test.integration.autochecklist_data.abcde import Foo
from test.integration.autochecklist_data.fail_then_succeed import RetryCounter
from test.mock import FixedDependencyProvider, MockMessenger
from typing import List, Optional, Set, Tuple

import autochecklist
from autochecklist import (
    BaseArgs,
    BaseConfig,
    ProblemLevel,
    TaskModel,
    TaskStatus,
    UserResponse,
)

_DATA_DIR = Path(__file__).parent.joinpath("autochecklist_data")
_LOG = _DATA_DIR.joinpath("test.log")


class TaskGraphTestCase(unittest.TestCase):
    def test_script_from_file(self) -> None:
        msg = MockMessenger(log_file=_LOG)
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[Foo(42)])
        tasks = _DATA_DIR.joinpath("abcde.json")
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=abcde,
        )
        self._check_status_trace(msg.mock_input_messenger.statuses, p=tasks, x=42)
        self.assertEqual([], msg.mock_input_messenger.errors)

    def test_script_from_model(self) -> None:
        msg = MockMessenger(log_file=_LOG)
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[Foo(99)])
        tasks = TaskModel(
            name="script_from_model",
            subtasks=[
                TaskModel(name="A", description="Task A", only_auto=True),
                TaskModel(
                    name="B", description="Task B", prerequisites={"A"}, only_auto=True
                ),
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
            module=abcde,
        )
        self._check_status_trace(msg.mock_input_messenger.statuses, p=None, x=99)
        self.assertEqual([], msg.mock_input_messenger.errors)

    def test_script_with_error(self) -> None:
        msg = MockMessenger(log_file=_LOG)
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[Foo(42)])
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
            module=abcde,
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

    def test_manual_task(self) -> None:
        def wait(
            task_name: str,
            index: Optional[int],
            prompt: str,
            allowed_responses: Set[UserResponse],
        ) -> UserResponse:
            self.assertEqual("manual", task_name)
            self.assertEqual("This task must be completed manually.", prompt)
            self.assertEqual({UserResponse.DONE, UserResponse.SKIP}, allowed_responses)
            return UserResponse.DONE

        msg = MockMessenger(log_file=_LOG)
        msg.mock_input_messenger.wait = wait
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[])
        tasks = TaskModel(
            name="manual",
            description="This task must be completed manually.",
        )
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=None,
        )
        expected_status_trace = [
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Loading tasks."),
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Running tasks."),
            ("manual", TaskStatus.NOT_STARTED, "-"),
            ("manual", TaskStatus.WAITING_FOR_USER, "This task is not automated."),
            ("manual", TaskStatus.DONE, "Task completed manually."),
            ("SCRIPT MAIN", TaskStatus.DONE, "All done!"),
            ("dependency_provider", TaskStatus.RUNNING, "Shut down."),
        ]
        self.assertEqual(expected_status_trace, msg.mock_input_messenger.statuses)
        self.assertEqual([], msg.mock_input_messenger.errors)

    def test_fail_and_retry(self) -> None:
        def wait(
            task_name: str,
            index: Optional[int],
            prompt: str,
            allowed_responses: Set[UserResponse],
        ) -> UserResponse:
            self.assertEqual("fail_then_succeed", task_name)
            self.assertEqual("This task will fail the first time.", prompt)
            self.assertEqual({UserResponse.RETRY, UserResponse.SKIP}, allowed_responses)
            return UserResponse.RETRY

        msg = MockMessenger(log_file=_LOG)
        msg.mock_input_messenger.wait = wait
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[RetryCounter()])
        tasks = TaskModel(
            name="fail_then_succeed",
            description="This task will fail the first time.",
            only_auto=True,
        )
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=fail_then_succeed,
        )
        expected_status_trace = [
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Loading tasks."),
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Running tasks."),
            ("fail_then_succeed", TaskStatus.NOT_STARTED, "-"),
            ("fail_then_succeed", TaskStatus.RUNNING, "Task started."),
            (
                "fail_then_succeed",
                TaskStatus.WAITING_FOR_USER,
                "The task automation failed. Requesting user input.",
            ),
            ("fail_then_succeed", TaskStatus.RUNNING, "Task started."),
            ("fail_then_succeed", TaskStatus.DONE, "Success!"),
            # Since the task logged its own status as DONE, the usual "Task
            # completed manually" message should be skipped.
            ("SCRIPT MAIN", TaskStatus.DONE, "All done!"),
            ("dependency_provider", TaskStatus.RUNNING, "Shut down."),
        ]
        self.assertEqual(expected_status_trace, msg.mock_input_messenger.statuses)
        self.assertEqual(
            [
                (
                    "fail_then_succeed",
                    ProblemLevel.ERROR,
                    "An error occurred while trying to complete the task automatically: Epic fail.",
                ),
            ],
            msg.mock_input_messenger.errors,
        )

    def test_fail_and_skip(self) -> None:
        def wait(
            task_name: str,
            index: Optional[int],
            prompt: str,
            allowed_responses: Set[UserResponse],
        ) -> UserResponse:
            self.assertEqual("fail_then_succeed", task_name)
            self.assertEqual("This task will fail the first time.", prompt)
            self.assertEqual(
                {UserResponse.DONE, UserResponse.RETRY, UserResponse.SKIP},
                allowed_responses,
            )
            return UserResponse.SKIP

        msg = MockMessenger(log_file=_LOG)
        msg.mock_input_messenger.wait = wait
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[RetryCounter()])
        tasks = TaskModel(
            name="fail_then_succeed",
            description="This task will fail the first time.",
        )
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=fail_then_succeed,
        )
        expected_status_trace = [
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Loading tasks."),
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Running tasks."),
            ("fail_then_succeed", TaskStatus.NOT_STARTED, "-"),
            ("fail_then_succeed", TaskStatus.RUNNING, "Task started."),
            (
                "fail_then_succeed",
                TaskStatus.WAITING_FOR_USER,
                "The task automation failed. Requesting user input.",
            ),
            ("fail_then_succeed", TaskStatus.SKIPPED, "Task skipped."),
            ("SCRIPT MAIN", TaskStatus.DONE, "All done!"),
            ("dependency_provider", TaskStatus.RUNNING, "Shut down."),
        ]
        self.assertEqual(expected_status_trace, msg.mock_input_messenger.statuses)
        self.assertEqual(
            [
                (
                    "fail_then_succeed",
                    ProblemLevel.ERROR,
                    "An error occurred while trying to complete the task automatically: Epic fail.",
                ),
            ],
            msg.mock_input_messenger.errors,
        )

    def test_keyboard_interrupt(self) -> None:
        msg = MockMessenger(log_file=_LOG)
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[])
        tasks = TaskModel(
            name="script_with_kbd_interrupt",
            subtasks=[
                TaskModel(name="keyboard_interrupt", description="Cancels everything."),
                TaskModel(
                    name="never_call_this",
                    description="Should not run",
                    prerequisites={"keyboard_interrupt"},
                ),
            ],
        )
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=keyboard_interrupt,
        )
        expected_status_trace = [
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Loading tasks."),
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Running tasks."),
            ("keyboard_interrupt", TaskStatus.NOT_STARTED, "-"),
            ("never_call_this", TaskStatus.NOT_STARTED, "-"),
            ("keyboard_interrupt", TaskStatus.RUNNING, "Task started."),
            # Maybe this should say something like "Script cancelled" instead.
            # But then again, if this happens then it means the user already
            # closed the window, so it doesn't really matter.
            ("SCRIPT MAIN", TaskStatus.DONE, "All done!"),
            ("dependency_provider", TaskStatus.RUNNING, "Shut down."),
        ]
        self.assertEqual(expected_status_trace, msg.mock_input_messenger.statuses)
        self.assertEqual([], msg.mock_input_messenger.errors)

    def test_cancel(self) -> None:
        def wait(
            task_name: str,
            index: Optional[int],
            prompt: str,
            allowed_responses: Set[UserResponse],
        ) -> UserResponse:
            self.assertEqual("cancel", task_name)
            self.assertEqual("Cancels one task.", prompt)
            self.assertEqual(
                {UserResponse.DONE, UserResponse.RETRY, UserResponse.SKIP},
                allowed_responses,
            )
            return UserResponse.DONE

        msg = MockMessenger(log_file=_LOG)
        msg.mock_input_messenger.wait = wait
        args = BaseArgs.parse([])
        config = BaseConfig()
        dep = FixedDependencyProvider(messenger=msg, args=[])
        tasks = TaskModel(
            name="script_with_cancel",
            subtasks=[
                TaskModel(name="cancel", description="Cancels one task."),
                TaskModel(
                    name="foo",
                    description="This task should run as usual.",
                    prerequisites={"cancel"},
                ),
            ],
        )
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=cancel,
        )
        expected_status_trace = [
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Loading tasks."),
            ("SCRIPT MAIN", TaskStatus.RUNNING, "Running tasks."),
            ("cancel", TaskStatus.NOT_STARTED, "-"),
            ("foo", TaskStatus.NOT_STARTED, "-"),
            ("cancel", TaskStatus.RUNNING, "Task started."),
            (
                "cancel",
                TaskStatus.WAITING_FOR_USER,
                "The task was cancelled by the user. Requesting user input.",
            ),
            ("cancel", TaskStatus.DONE, "Task completed manually."),
            ("foo", TaskStatus.RUNNING, "Task started."),
            ("foo", TaskStatus.RUNNING, "foo running as usual."),
            ("foo", TaskStatus.DONE, "Task completed automatically."),
            ("SCRIPT MAIN", TaskStatus.DONE, "All done!"),
            ("dependency_provider", TaskStatus.RUNNING, "Shut down."),
        ]
        self.assertEqual(expected_status_trace, msg.mock_input_messenger.statuses)
        self.assertEqual([], msg.mock_input_messenger.errors)

    def _check_status_trace(
        self, status_trace: List[Tuple[str, TaskStatus, str]], p: Optional[Path], x: int
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
            ("A", TaskStatus.RUNNING, f"Running A with x = {x}"),
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
