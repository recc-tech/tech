"""
Type definitions for the `InputMessenger` interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from threading import Thread
from typing import Callable, Dict, Generic, List, Optional, Set, TypeVar

T = TypeVar("T")


@dataclass
class ListChoice(Generic[T]):
    """
    One option that the user can choose when presented with a list of options.
    """

    value: T
    """The value associated with this choice."""
    display: str
    """What to show the user."""


class InputMessenger:
    def start(self, after_start: Callable[[], None]) -> None:
        def run_main_worker() -> None:
            self.wait_for_start()
            after_start()

        main_worker_thread = Thread(name="MainWorker", target=run_main_worker)
        main_worker_thread.start()
        self.run_main_loop()

    def run_main_loop(self) -> None:
        raise NotImplementedError()

    def wait_for_start(self) -> None:
        raise NotImplementedError()

    @property
    def is_closed(self) -> bool:
        raise NotImplementedError()

    def close(self) -> None:
        raise NotImplementedError()

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        raise NotImplementedError()

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        raise NotImplementedError()

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> T:
        raise NotImplementedError()

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        raise NotImplementedError()

    def input_bool(self, prompt: str, title: str = "") -> bool:
        raise NotImplementedError()

    def input_from_list(
        self, choices: List[ListChoice[T]], prompt: str, title: str = ""
    ) -> Optional[T]:
        raise NotImplementedError()

    def wait(
        self,
        task_name: str,
        index: Optional[int],
        prompt: str,
        allowed_responses: Set[UserResponse],
    ) -> UserResponse:
        raise NotImplementedError()

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        raise NotImplementedError()

    def remove_command(self, task_name: str, command_name: str) -> None:
        raise NotImplementedError()

    def create_progress_bar(
        self, display_name: str, max_value: float, units: str
    ) -> int:
        raise NotImplementedError()

    def update_progress_bar(self, key: int, progress: float) -> None:
        raise NotImplementedError()

    def delete_progress_bar(self, key: int) -> None:
        raise NotImplementedError()


@dataclass
class Parameter:
    display_name: str
    parser: Callable[[str], object] = lambda x: x
    password: bool = False
    description: str = ""
    default: str = ""


class TaskStatus(Enum):
    NOT_STARTED = auto()
    """The task has not yet started."""
    RUNNING = auto()
    """The automatic implementation of the task is running."""
    WAITING_FOR_USER = auto()
    """Waiting for user input."""
    DONE = auto()
    """Task completed, either manually or automatically."""
    SKIPPED = auto()
    """Task skipped."""

    def __str__(self):
        return self.name


class ProblemLevel(Enum):
    WARN = auto()
    """
    Something that may cause incorrect behaviour, but does not immediately
    prevent the current task from continuing.
    """
    ERROR = auto()
    """
    A problem that prevents the current task from completing successfully.
    """
    FATAL = auto()
    """
    A problem that forces the entire program to exit.
    """

    def to_log_level(self) -> int:
        if self == ProblemLevel.WARN:
            return logging.WARN
        elif self == ProblemLevel.ERROR:
            return logging.ERROR
        elif self == ProblemLevel.FATAL:
            return logging.FATAL
        else:
            # This should never happen, but just in case
            return logging.ERROR

    def __str__(self):
        return self.name


class UserResponse(Enum):
    """User's response to a task needing to be completed manually."""

    DONE = auto()
    """The task has been completed manually."""
    RETRY = auto()
    """The task automation should be re-run."""
    SKIP = auto()
    """The task will not be completed."""

    def __str__(self) -> str:
        return self.name
