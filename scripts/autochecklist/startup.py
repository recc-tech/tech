import sys
import traceback
from pathlib import Path
from typing import Callable, Tuple, Union

from .base_config import BaseConfig
from .messenger import Messenger, ProblemLevel, TaskStatus
from .task import FunctionFinder, TaskGraph, TaskModel


def run(
    error_file: Path,
    create_messenger: Callable[[], Messenger],
    create_services: Callable[
        [Messenger], Tuple[Union[TaskModel, Path], FunctionFinder, BaseConfig]
    ],
    success_message: str = "All done!",
) -> None:
    # If the program is being run *without* a terminal window, then redirect
    # stderr to the given file.
    # This ensures errors that would normally be printed to the terminal do not
    # silently kill the program.

    # pythonw sets sys.stderr to None.
    # Open the file even when not using pythonw for easier debugging.
    with open(error_file, "w", encoding="utf-8") as se:
        has_terminal = sys.stderr is not None  # type: ignore
        if has_terminal:
            _run_main(create_messenger, create_services, success_message)
        else:
            sys.stderr = se
            _run_main(create_messenger, create_services, success_message)
    # No need to keep the file around if the program exited successfully and
    # it's empty
    try:
        with open(error_file, "r", encoding="utf-8") as f:
            text = f.read()
        if len(text) == 0:
            error_file.unlink(missing_ok=True)
    except:
        pass


def _run_main(
    create_messenger: Callable[[], Messenger],
    create_services: Callable[
        [Messenger], Tuple[Union[TaskModel, Path], FunctionFinder, BaseConfig]
    ],
    success_message: str = "All done!",
) -> None:
    try:
        messenger = create_messenger()
    except Exception as e:
        print(f"Failed to create messenger: {e}", file=sys.stderr)
        return

    try:
        messenger.start(
            after_start=lambda m: _run_worker(m, create_services, success_message)
        )
    except Exception as e:
        print(f"Failed to start messenger: {e}", file=sys.stderr)


def _run_worker(
    messenger: Messenger,
    create_services: Callable[
        [Messenger], Tuple[Union[TaskModel, Path], FunctionFinder, BaseConfig]
    ],
    success_message: str,
) -> None:
    try:
        try:
            task_model, function_finder, config = create_services(messenger)
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to create services: {e}",
                traceback.format_exc(),
            )
            messenger.log_status(TaskStatus.DONE, "Script failed.")
            return

        try:
            messenger.log_status(TaskStatus.RUNNING, "Loading task graph.")
            if isinstance(task_model, Path):
                task_model = TaskModel.load(task_model)
            task_graph = TaskGraph(task_model, messenger, function_finder, config)
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to load the task graph: {e}",
                traceback.format_exc(),
            )
            messenger.log_status(TaskStatus.DONE, "Script failed.")
            return

        try:
            messenger.log_status(TaskStatus.RUNNING, "Running tasks.")
            task_graph.run()
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to run the tasks: {e}",
                traceback.format_exc(),
            )
            messenger.log_status(TaskStatus.DONE, "Script failed.")
            return

        messenger.log_status(TaskStatus.DONE, success_message)
    except KeyboardInterrupt:
        pass
    finally:
        messenger.close()
