import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple, TypeVar

from autochecklist import (
    FileMessenger,
    InputMessenger,
    Messenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
    UserResponse,
)

T = TypeVar("T")


class MockInputMessenger(InputMessenger):
    def __init__(self) -> None:
        self.errors: List[Tuple[str, ProblemLevel, str]] = []
        self.statuses: List[Tuple[str, TaskStatus, str]] = []
        self.close_event = threading.Event()

    @property
    def is_closed(self) -> bool:
        return self.close_event.is_set()

    def close(self) -> None:
        self.close_event.set()

    def wait_for_start(self) -> None:
        pass

    def run_main_loop(self) -> None:
        self.close_event.wait()

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        self.errors.append((task_name, level, message))

    def log_status(
        self,
        task_name: str,
        index: Optional[int],
        status: TaskStatus,
        message: str,
    ) -> None:
        self.statuses.append((task_name, status, message))

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> T:
        raise NotImplementedError(
            "Taking input is not supported during automated tests."
        )

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        raise NotImplementedError(
            "Taking input is not supported during automated tests."
        )

    def input_bool(self, prompt: str, title: str = "") -> bool:
        raise NotImplementedError(
            "Taking input is not supported during automated tests."
        )

    def wait(
        self,
        task_name: str,
        index: Optional[int],
        prompt: str,
        allowed_responses: Set[UserResponse],
    ) -> UserResponse:
        raise NotImplementedError(
            "Taking input is not supported during automated tests."
        )

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        pass

    def remove_command(self, task_name: str, command_name: str) -> None:
        pass

    def create_progress_bar(
        self, display_name: str, max_value: float, units: str
    ) -> int:
        return 0

    def update_progress_bar(self, key: int, progress: float) -> None:
        pass

    def delete_progress_bar(self, key: int) -> None:
        pass


class MockMessenger(Messenger):
    def __init__(self, log_file: Path) -> None:
        self.mock_input_messenger = MockInputMessenger()
        file_messenger = FileMessenger(log_file)
        super().__init__(file_messenger, self.mock_input_messenger)
