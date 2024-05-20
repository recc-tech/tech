import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Optional, Union

from .base_args import BaseArgs
from .base_config import BaseConfig
from .messenger import Messenger, ProblemLevel, TaskStatus
from .task import DependencyProvider, FunctionFinder, TaskGraph, TaskModel

_ERROR_FILE = Path("error.log")
_SUCCESS_MESSAGE = "All done!"
_FAIL_MESSAGE = "Script failed."


def run(
    args: BaseArgs,
    config: BaseConfig,
    dependency_provider: DependencyProvider,
    tasks: Union[Path, TaskModel],
    module: Optional[ModuleType],
) -> None:
    # If the program is being run *without* a terminal window, then redirect
    # stderr to the given file.
    # This ensures errors that would normally be printed to the terminal do not
    # silently kill the program.

    # pythonw sets sys.stderr to None.
    # Open the file even when not using pythonw for easier debugging.
    with open(_ERROR_FILE, "w", encoding="utf-8") as se:
        has_terminal = (
            sys.stderr is not None  # pyright: ignore[reportUnnecessaryComparison]
        )
        if has_terminal:
            _run_main(
                args=args,
                config=config,
                tasks=tasks,
                module=module,
                dependency_provider=dependency_provider,
            )
        else:
            sys.stderr = se
            _run_main(
                args=args,
                config=config,
                tasks=tasks,
                module=module,
                dependency_provider=dependency_provider,
            )
    # No need to keep the file around if the program exited successfully and
    # it's empty
    try:
        with open(_ERROR_FILE, "r", encoding="utf-8") as f:
            text = f.read()
        if len(text) == 0:
            _ERROR_FILE.unlink(missing_ok=True)
    except:
        pass


def _run_main(
    args: BaseArgs,
    config: BaseConfig,
    tasks: Union[Path, TaskModel],
    module: Optional[ModuleType],
    dependency_provider: DependencyProvider,
) -> None:
    messenger = dependency_provider.messenger
    try:
        messenger.start(
            after_start=lambda: _run_worker(
                args=args,
                config=config,
                messenger=messenger,
                tasks=tasks,
                module=module,
                dependency_provider=dependency_provider,
            )
        )
    except Exception as e:
        raise RuntimeError(f"Failed to run messenger: {e}") from e


def _run_worker(
    args: BaseArgs,
    config: BaseConfig,
    messenger: Messenger,
    tasks: Union[Path, TaskModel],
    module: Optional[ModuleType],
    dependency_provider: DependencyProvider,
) -> None:
    try:
        try:
            messenger.log_status(TaskStatus.RUNNING, "Creating services.")
            function_finder = FunctionFinder(
                module=module,
                dependency_provider=dependency_provider,
                messenger=messenger,
            )
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to create services: {e}",
                traceback.format_exc(),
            )
            messenger.log_status(TaskStatus.DONE, _FAIL_MESSAGE)
            return

        try:
            if isinstance(tasks, Path):
                messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Loading tasks from {tasks.as_posix()}.",
                )
                tasks = TaskModel.load(tasks)
            messenger.log_status(TaskStatus.RUNNING, "Loading task graph.")
            task_graph = TaskGraph(tasks, messenger, function_finder, args, config)
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to load the task graph: {e}",
                traceback.format_exc(),
            )
            messenger.log_status(TaskStatus.DONE, _FAIL_MESSAGE)
            return

        if args.no_run:
            messenger.log_status(
                TaskStatus.DONE, "No tasks were run because no_run = true."
            )
        else:
            try:
                messenger.log_status(TaskStatus.RUNNING, "Running tasks.")
                task_graph.run()
                messenger.log_status(TaskStatus.DONE, _SUCCESS_MESSAGE)
            except Exception as e:
                messenger.log_problem(
                    ProblemLevel.FATAL,
                    f"Failed to run the tasks: {e} ({type(e).__name__})",
                    traceback.format_exc(),
                )
                messenger.log_status(TaskStatus.DONE, _FAIL_MESSAGE)
                return
    except KeyboardInterrupt:
        pass
    finally:
        messenger.close()
        # TODO: Test that this actually gets called in either case!
        dependency_provider.shut_down()
