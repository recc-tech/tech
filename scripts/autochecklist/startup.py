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
_STARTUP_FILE = Path("startup.txt")
_SUCCESS_MESSAGE = "All done!"
_FAIL_MESSAGE = "Script failed."


def run(
    args: BaseArgs,
    config: BaseConfig,
    dependency_provider: DependencyProvider,
    tasks: Union[Path, TaskModel],
    module: Optional[ModuleType],
    allow_unused_functions: bool = False,
) -> None:
    # If the program is being run *without* a terminal window, then redirect
    # stderr to the given file.
    # This ensures errors that would normally be printed to the terminal do not
    # silently kill the program.

    # pythonw sets sys.stderr to None.
    # Open the file even when not using pythonw for easier debugging.
    with open(_ERROR_FILE, "w", encoding="utf-8") as se:
        has_terminal = sys.stderr is not None
        if has_terminal:
            _run_main(
                args=args,
                config=config,
                tasks=tasks,
                module=module,
                dependency_provider=dependency_provider,
                allow_unused_functions=allow_unused_functions,
            )
        else:
            sys.stderr = se
            _run_main(
                args=args,
                config=config,
                tasks=tasks,
                module=module,
                dependency_provider=dependency_provider,
                allow_unused_functions=allow_unused_functions,
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
    allow_unused_functions: bool,
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
                allow_unused_functions=allow_unused_functions,
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
    allow_unused_functions: bool,
) -> None:
    try:
        try:
            _STARTUP_FILE.unlink(missing_ok=True)
        except Exception as e:
            print(f"Failed to delete {_STARTUP_FILE}.", file=sys.stderr)

        try:
            if isinstance(tasks, Path):
                messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Loading tasks from {tasks.as_posix()}.",
                )
                tasks = TaskModel.load(tasks)
            else:
                messenger.log_status(TaskStatus.RUNNING, "Loading tasks.")
            function_finder = FunctionFinder(
                module=module,
                dependency_provider=dependency_provider,
                messenger=messenger,
                allow_unused_functions=allow_unused_functions,
            )
            task_graph = TaskGraph(
                tasks,
                messenger,
                function_finder,
                args,
                config,
            )
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
        # The integration tests in test_autochecklist_run.py depend on the
        # dependency provider being able to use the messenger (maybe a bit
        # sketchy, but whatever). Therefore, call shut_down() before closing
        # the messenger.
        dependency_provider.shut_down()
        messenger.close()
