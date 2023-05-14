from __future__ import annotations
from logging import DEBUG, INFO, WARN
from pathlib import Path
from threading import Thread
from typing import Callable, List

from messenger import Messenger


class Task:
    """
    Represents a single, independent task.
    """

    _run: Callable[[], None]
    """
    Function which performs the given task, but without logging or exception handling.
    """

    _fallback_message: str
    """
    Instructions to show to the user in case the function raises an exception.
    """

    _messenger: Messenger
    """
    Messenger to use for logging and input.
    """

    def __init__(
        self, func: Callable[[], None], fallback_message: str, messenger: Messenger
    ):
        self._run = func
        self._fallback_message = fallback_message
        self._messenger = messenger

    def run(self):
        self._messenger.log(DEBUG, f"Running task '{self._run.__name__}'.")
        try:
            self._run()
            self._messenger.log(
                INFO, f"Task '{self._run.__name__}' completed successfully."
            )
        except Exception as e:
            if isinstance(e, NotImplementedError):
                self._messenger.log(
                    DEBUG,
                    f"Task '{self._run.__name__}' is not yet implemented. Requesting user input.",
                )
            else:
                self._messenger.log(
                    WARN,
                    f"Task '{self._run.__name__}' failed with an exception: {e}",
                )

            message = f"{self._fallback_message} When you are done, press ENTER."
            self._messenger.wait_for_input(message)


class TaskThread(Thread):
    """
    Represents a sequence of tasks.
    """

    def __init__(
        self,
        name: str,
        tasks: List[Task],
        prerequisites: List[TaskThread] = [],
    ):
        if not tasks:
            raise ValueError("A thread must have at least one task to perform.")
        self.tasks = tasks
        self.prerequisites = prerequisites
        super().__init__(name=name)

    def run(self):
        # Wait for prerequisites
        for p in self.prerequisites:
            p.join()

        # Run tasks
        for t in self.tasks:
            t.run()


class TaskGraph:
    @staticmethod
    def load(file: Path) -> TaskGraph:
        raise NotImplementedError()

    def run(self) -> None:
        raise NotImplementedError()
