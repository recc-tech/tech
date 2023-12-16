"""
Provides access to JavaScript functions required by the eel messenger in a more
type-safe way.
"""
# pyright: basic, reportGeneralTypeIssues=false
from typing import Dict, Optional

import eel

from .input_messenger import Parameter, ProblemLevel, TaskStatus


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


def show_bool_input_dialog(prompt: str, title: str) -> None:
    eel.show_bool_input_dialog(prompt, title)


def show_input_dialog(
    title: str,
    prompt: str,
    params: Dict[str, Parameter],
    error_messages: Dict[str, str],
) -> None:
    eel.show_input_dialog(
        title,
        prompt,
        {
            t: {
                "display_name": p.display_name,
                "password": p.password,
                "description": p.description,
                "default": p.default,
                "error_message": error_messages[t] if t in error_messages else "",
            }
            for (t, p) in params.items()
        },
    )


def add_action_item(
    task_name: str, index: Optional[int], prompt: str, allow_retry: bool
) -> None:
    eel.add_action_item(task_name, index, prompt, allow_retry)


def remove_action_item(task_name: str) -> None:
    eel.remove_action_item(task_name)


def add_command(task_name: str, command_name: str) -> None:
    eel.add_command(task_name, command_name)


def remove_command(task_name: str, command_name: str) -> None:
    eel.remove_command(task_name, command_name)
