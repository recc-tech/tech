import sys
import traceback
from pathlib import Path
from typing import Generic, Tuple, TypeVar, Union

from .base_args import BaseArgs
from .base_config import BaseConfig
from .messenger import (
    ConsoleMessenger,
    FileMessenger,
    Messenger,
    ProblemLevel,
    TaskStatus,
    TkMessenger,
)
from .task import FunctionFinder, TaskGraph, TaskModel

A = TypeVar("A", bound=BaseArgs)
C = TypeVar("C", bound=BaseConfig)


class Script(Generic[A, C]):
    def parse_args(self) -> A:
        raise NotImplementedError()

    def create_config(self, args: A) -> C:
        raise NotImplementedError()

    def create_messenger(self, args: A, config: C) -> Messenger:
        raise NotImplementedError()

    def create_services(
        self, args: A, config: C, messenger: Messenger
    ) -> Tuple[Union[TaskModel, Path], FunctionFinder]:
        raise NotImplementedError()

    def shut_down(self, args: A, config: C) -> None:
        pass

    @property
    def success_message(self) -> str:
        return "All done!"

    @property
    def fail_message(self) -> str:
        return "Script failed."

    @property
    def error_file(self) -> Path:
        return Path("error.log")

    def run(self) -> None:
        # If the program is being run *without* a terminal window, then redirect
        # stderr to the given file.
        # This ensures errors that would normally be printed to the terminal do not
        # silently kill the program.

        # pythonw sets sys.stderr to None.
        # Open the file even when not using pythonw for easier debugging.
        with open(self.error_file, "w", encoding="utf-8") as se:
            has_terminal = sys.stderr is not None
            if has_terminal:
                self._run_main()
            else:
                sys.stderr = se
                self._run_main()
        # No need to keep the file around if the program exited successfully and
        # it's empty
        try:
            with open(self.error_file, "r", encoding="utf-8") as f:
                text = f.read()
            if len(text) == 0:
                self.error_file.unlink(missing_ok=True)
        except:
            pass

    def _run_main(self) -> None:
        try:
            args = self.parse_args()
        except Exception as e:
            raise RuntimeError(f"Failed to parse command-line arguments.") from e

        try:
            config = self.create_config(args)
        except Exception as e:
            raise RuntimeError(f"Failed to load config.") from e

        try:
            messenger = self.create_messenger(args, config)
        except Exception as e:
            raise RuntimeError(f"Failed to create user interface.") from e

        try:
            messenger.start(
                after_start=lambda: self._run_worker(args, config, messenger)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to run messenger: {e}") from e

    def _run_worker(self, args: A, config: C, messenger: Messenger) -> None:
        try:
            try:
                messenger.log_status(TaskStatus.RUNNING, "Creating services.")
                task_model, function_finder = self.create_services(
                    args, config, messenger
                )
            except Exception as e:
                messenger.log_problem(
                    ProblemLevel.FATAL,
                    f"Failed to create services: {e}",
                    traceback.format_exc(),
                )
                messenger.log_status(TaskStatus.DONE, self.fail_message)
                return

            try:
                if isinstance(task_model, Path):
                    messenger.log_status(
                        TaskStatus.RUNNING,
                        f"Loading tasks from {task_model.as_posix()}.",
                    )
                    task_model = TaskModel.load(task_model)
                messenger.log_status(TaskStatus.RUNNING, "Loading task graph.")
                task_graph = TaskGraph(
                    task_model, messenger, function_finder, args, config
                )
            except Exception as e:
                messenger.log_problem(
                    ProblemLevel.FATAL,
                    f"Failed to load the task graph: {e}",
                    traceback.format_exc(),
                )
                messenger.log_status(TaskStatus.DONE, self.fail_message)
                return

            if args.no_run:
                messenger.log_status(
                    TaskStatus.DONE, "No tasks were run because config.no_run = true."
                )
            else:
                try:
                    messenger.log_status(TaskStatus.RUNNING, "Running tasks.")
                    task_graph.run()
                    messenger.log_status(TaskStatus.DONE, self.success_message)
                except Exception as e:
                    messenger.log_problem(
                        ProblemLevel.FATAL,
                        f"Failed to run the tasks: {e}",
                        traceback.format_exc(),
                    )
                    messenger.log_status(TaskStatus.DONE, self.fail_message)
                    return
        except KeyboardInterrupt:
            pass
        finally:
            messenger.close()
            self.shut_down(args, config)


class DefaultScript(Script[BaseArgs, BaseConfig]):
    def parse_args(self) -> BaseArgs:
        return BaseArgs.parse(sys.argv)

    def create_config(self, args: BaseArgs) -> BaseConfig:
        return BaseConfig()

    def create_messenger(self, args: BaseArgs, config: BaseConfig) -> Messenger:
        file_messenger = FileMessenger(Path("autochecklist.log"))
        input_messenger = (
            TkMessenger(
                "Autochecklist", "", theme="dark", show_statuses_by_default=False
            )
            if args.ui == "tk"
            else ConsoleMessenger("", show_task_status=args.verbose)
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, args: BaseArgs, config: BaseConfig, messenger: Messenger
    ) -> Tuple[Union[Path, TaskModel], FunctionFinder]:
        function_finder = FunctionFinder(module=None, arguments=[], messenger=messenger)
        return Path("tasks.json"), function_finder

    def shut_down(self, args: BaseArgs, config: BaseConfig) -> None:
        pass
