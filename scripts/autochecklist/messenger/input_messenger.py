"""
Type definitions for the `InputMessenger` interface.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class InputMessenger:
    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        raise NotImplementedError()

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        raise NotImplementedError()

    def close(self, wait: bool):
        """
        Performs any cleanup that is required before exiting (e.g., making worker threads exit).
        """
        pass

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

    def wait(self, task_name: str, index: Optional[int], prompt: str) -> None:
        raise NotImplementedError()

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        raise NotImplementedError()

    def remove_command(self, task_name: str, command_name: str) -> None:
        raise NotImplementedError()


@dataclass
class Parameter:
    display_name: str
    parser: Callable[[str], object] = lambda x: x
    password: bool = False
    description: str = ""


class TaskStatus(Enum):
    NOT_STARTED = auto()
    """
    The task has not yet started.
    """
    RUNNING = auto()
    """
    The automatic implementation of the task is running.
    """
    WAITING_FOR_USER = auto()
    """
    Waiting for user input.
    """
    DONE = auto()
    """
    Task completed, either manually or automatically.
    """

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


def is_current_thread_main() -> bool:
    return threading.current_thread() is threading.main_thread()


def interrupt_main_thread():
    os.kill(os.getpid(), signal.CTRL_C_EVENT)
    # TODO: This is probably just a race condition in the console messenger
    # It seems like the signal isn't delivered until print() is
    # called! But printing nothing doesn't work.
    print(" ", end="", flush=True)
    # TODO: Should I have this function call taskkill /f as a fallback if
    # close() isn't called within 5 seconds?
