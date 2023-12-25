"""
Provides access to JavaScript functions required by the eel messenger in a more
type-safe way.
"""
# pyright: basic, reportGeneralTypeIssues=false
from typing import Dict, Optional, Set

import eel

from .input_messenger import Parameter, ProblemLevel, TaskStatus, UserResponse


def set_title(title: str) -> None:
    eel.set_title(title)


def set_description(description: str) -> None:
    eel.set_description(description)


def log_status(
    task_name: str, index: Optional[int], status: TaskStatus, message: str
) -> None:
    eel.log_status(task_name, index, str(status), message)


def log_problem(task_name: str, level: ProblemLevel, message: str) -> None:
    eel.log_problem(task_name, str(level), message)


def show_bool_input_dialog(key: int, prompt: str, title: str) -> None:
    eel.show_bool_input_dialog(key, prompt, title)


def show_input_dialog(
    key: int,
    title: str,
    prompt: str,
    params: Dict[str, Parameter],
    error_messages: Dict[str, str],
) -> None:
    eel.show_input_dialog(
        key,
        title,
        prompt,
        {
            t: {
                "label": p.display_name,
                "is_password": p.password,
                "description": p.description,
                "default": p.default,
                "error_message": error_messages[t] if t in error_messages else "",
            }
            for (t, p) in params.items()
        },
    )


def add_action_item(
    task_name: str,
    index: Optional[int],
    prompt: str,
    allowed_responses: Set[UserResponse],
) -> None:
    eel.add_action_item(task_name, index, prompt, [str(r) for r in allowed_responses])


def add_command(task_name: str, command_name: str) -> None:
    eel.add_command(task_name, command_name)


def remove_command(task_name: str, command_name: str) -> None:
    eel.remove_command(task_name, command_name)


def show_script_done_message() -> None:
    eel.show_script_done_message()


def create_progress_bar(display_name: str, max_value: float, units: str) -> int:
    return eel.create_progress_bar(display_name, max_value, units)()


def update_progress_bar(key: int, progress: float) -> None:
    eel.update_progress_bar(key, progress)


def delete_progress_bar(key: int) -> None:
    eel.delete_progress_bar(key)
