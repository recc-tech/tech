from __future__ import annotations

import logging
from logging import FileHandler
from pathlib import Path
from threading import Lock, local
from typing import Callable, Dict, Optional, TypeVar

from autochecklist.messenger.input_messenger import (
    InputMessenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
)

T = TypeVar("T")

# TODO: Use other synchronization primitives (e.g., Event, Condition) rather
# than using Lock everywhere?
# TODO: Write automated tests (cancelling the program is especially tricky to
# get right)


class Messenger:
    """Thread-safe class for logging and user interactions."""

    ROOT_PSEUDOTASK_NAME = "SCRIPT MAIN"
    """Default display name for the main thread."""

    def __init__(self, file_messenger: FileMessenger, input_messenger: InputMessenger):
        self._file_messenger = file_messenger
        self._input_messenger = input_messenger
        self._task_manager = _TaskManager()
        self._task_manager_mutex = Lock()
        self.set_current_task_name(self.ROOT_PSEUDOTASK_NAME)

    def set_current_task_name(self, task_name: Optional[str]):
        with self._task_manager_mutex:
            self._task_manager.set_current_task_name(task_name)

    def set_task_index_table(self, task_index_table: Dict[str, int]):
        with self._task_manager_mutex:
            self._task_manager.set_task_index_table(task_index_table)

    def log_debug(self, message: str, task_name: str = ""):
        with self._task_manager_mutex:
            task_name = self._task_manager.get_task_name(task_name) or "UNKNOWN"
        self._file_messenger.log(
            task_name=task_name,
            level=logging.DEBUG,
            message=message,
        )

    def log_status(
        self,
        status: TaskStatus,
        message: str,
        task_name: str = "",
        file_only: bool = False,
    ):
        with self._task_manager_mutex:
            actual_task_name = self._task_manager.get_task_name(task_name)
            if actual_task_name:
                task_name_for_display = actual_task_name
                index = self._task_manager.get_index(actual_task_name)
            else:
                task_name_for_display = "UNKNOWN"
                index = None
        log_message = f"Task status: {status}. {message}"
        self._file_messenger.log(task_name_for_display, logging.INFO, log_message)
        if not file_only:
            self._input_messenger.log_status(
                task_name_for_display, index, status, message
            )

    # TODO: It would be nice to show not only the exception but the exception
    # type. For example, `str(key_error)` may just show `the_key` when
    # `KeyError: 'the_key'` would be clearer. Ideally the solution should be
    # easy to use everywhere without copy-pasting.
    def log_problem(
        self,
        level: ProblemLevel,
        message: str,
        stacktrace: str = "",
        task_name: str = "",
    ):
        with self._task_manager_mutex:
            task_name = self._task_manager.get_task_name(task_name) or "UNKNOWN"
        details = f"\n{stacktrace}" if stacktrace else ""
        self._file_messenger.log(task_name, level.to_log_level(), f"{message}{details}")
        self._input_messenger.log_problem(task_name, level, message)

    def input(
        self,
        display_name: str,
        password: bool = False,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> Optional[T]:
        return self._input_messenger.input(
            display_name, password, parser, prompt, title
        )

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        return self._input_messenger.input_multiple(params, prompt, title)

    def wait(self, prompt: str, task_name: str = ""):
        with self._task_manager_mutex:
            actual_task_name = self._task_manager.get_task_name(task_name)
            if actual_task_name:
                task_name_for_display = actual_task_name
                index = self._task_manager.get_index(actual_task_name)
            else:
                task_name_for_display = "UNKNOWN"
                index = None
        self._input_messenger.wait(task_name_for_display, index, prompt)

    def allow_cancel(self, task_name: str = "") -> CancellationToken:
        """
        Allow the user to cancel a task.
        """
        with self._task_manager_mutex:
            actual_task_name = self._task_manager.get_task_name(task_name)
            if not actual_task_name:
                self.log_debug(
                    message="Could not allow cancelling because the current task is unknown and no task name was provided.",
                    task_name="UNKNOWN",
                )
                return CancellationToken()
            token = self._task_manager.get_cancellation_token(actual_task_name)
            # Avoid generating multiple tokens for one task, otherwise the user
            # might cancel and not have every piece of code be notified
            if not token:
                token = CancellationToken()
            self._task_manager.set_cancellation_token(actual_task_name, token)

        def callback():
            # TODO: messagebox is not defined
            should_cancel = messagebox.askyesno(  # type: ignore
                title="Confirm cancel",
                message="Are you sure you want to cancel the automation for this task? You will be asked to complete the task manually instead.",
            )
            if not should_cancel:
                return
            token.cancel()
            self.log_status(
                status=TaskStatus.RUNNING,
                message="Cancelling task...",
                task_name=actual_task_name or "",
            )
            self.disallow_cancel(task_name=actual_task_name or "")

        try:
            self._input_messenger.add_command(
                task_name=actual_task_name,
                command_name="Cancel",
                callback=callback,
            )
        except NotImplementedError:
            self.log_debug(
                message="Could not allow cancelling because the input messenger does not support it.",
                task_name=actual_task_name,
            )
        return token

    def disallow_cancel(self, task_name: str = ""):
        """
        Remove the ability to cancel a task if cancelling was allowed.
        """
        with self._task_manager_mutex:
            actual_task_name = self._task_manager.get_task_name(task_name)
            if not actual_task_name:
                self.log_debug(
                    message="Could not disallow cancelling because the current task is unknown and no task name was provided.",
                    task_name=task_name,
                )
                return
        try:
            self._input_messenger.remove_command(
                task_name=actual_task_name, command_name="Cancel"
            )
        except NotImplementedError:
            self.log_debug(
                message="Could not disallow cancelling because the input messenger does not support it.",
                task_name=actual_task_name,
            )

    def close(self, wait: bool):
        """
        If `wait` is `False`, the messenger will stop immediately, (as opposed
        to, for example, finishing IO operations that were started but not yet
        completed or waiting for the user to close the window.
        """
        self._input_messenger.close(wait)


class CancellationToken:
    def __init__(self):
        self._is_cancelled = False
        self._mutex = Lock()

    def cancel(self):
        with self._mutex:
            self._is_cancelled = True

    def raise_if_cancelled(self):
        with self._mutex:
            if self._is_cancelled:
                raise TaskCancelledException()


# Subclass `BaseException` so that code that catches `Exception` doesn't
# accidentally catch this
class TaskCancelledException(BaseException):
    pass


class _TaskManager:
    """
    Keep track of the current task by thread and provide access to relevant
    metadata for tasks.
    """

    class _Local(local):
        current_task_name: Optional[str] = None

    def __init__(self):
        self._local = self._Local()
        # Put the root "task" (e.g., the script startup code) at the top by
        # default
        self._index_by_task = {Messenger.ROOT_PSEUDOTASK_NAME: 0}
        self._cancellation_token_by_task: Dict[str, CancellationToken] = {}

    def set_current_task_name(self, task_name: Optional[str]):
        self._local.current_task_name = task_name

    def set_task_index_table(self, task_index_table: Dict[str, int]):
        # Don't mutate the input
        self._index_by_task = dict(task_index_table)
        # Let the client override the default placement of the root "task"
        # if they want to
        if Messenger.ROOT_PSEUDOTASK_NAME not in self._index_by_task:
            self._index_by_task[Messenger.ROOT_PSEUDOTASK_NAME] = 0

    def get_task_name(self, task_name: str) -> Optional[str]:
        return task_name if task_name else self._local.current_task_name

    def get_index(self, task_name: str) -> Optional[int]:
        return (
            self._index_by_task[task_name]
            if task_name and task_name in self._index_by_task
            else None
        )

    def get_cancellation_token(self, task_name: str) -> Optional[CancellationToken]:
        return (
            self._cancellation_token_by_task[task_name]
            if task_name in self._cancellation_token_by_task
            else None
        )

    def set_cancellation_token(self, task_name: str, token: CancellationToken):
        self._cancellation_token_by_task[task_name] = token


class FileMessenger:
    def __init__(self, log_file: Path):
        if not log_file.exists():
            log_file.parent.mkdir(exist_ok=True, parents=True)
        handler = FileHandler(log_file)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(
                fmt="[%(levelname)-8s] [%(asctime)s] %(message)s",
                datefmt="%H:%M:%S",
            ),
        )
        self._file_logger = logging.getLogger("file_messenger")
        self._file_logger.setLevel(logging.DEBUG)
        self._file_logger.addHandler(handler)

    def log(self, task_name: str, level: int, message: str):
        self._file_logger.log(level=level, msg=f"[{task_name:<35}] {message}")
