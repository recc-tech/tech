import sys
import traceback
from pathlib import Path
from typing import Generic, Tuple, TypeVar, Union

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

TConfig = TypeVar("TConfig", bound=BaseConfig)


class Script(Generic[TConfig]):
    def create_config(self) -> TConfig:
        raise NotImplementedError()

    def create_messenger(self, config: TConfig) -> Messenger:
        raise NotImplementedError()

    def create_services(
        self, config: TConfig, messenger: Messenger
    ) -> Tuple[Union[TaskModel, Path], FunctionFinder]:
        raise NotImplementedError()

    def shut_down(self, config: TConfig) -> None:
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
            has_terminal = (
                sys.stderr is not None  # pyright: ignore[reportUnnecessaryComparison]
            )
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
            config = self.create_config()
        except Exception as e:
            print(f"Failed to create config: {e}", file=sys.stderr)
            return

        try:
            messenger = self.create_messenger(config)
        except Exception as e:
            print(f"Failed to create messenger: {e}", file=sys.stderr)
            return

        try:
            messenger.start(after_start=lambda: self._run_worker(config, messenger))
        except Exception as e:
            print(f"Failed to run messenger: {e}", file=sys.stderr)

    def _run_worker(self, config: TConfig, messenger: Messenger) -> None:
        try:
            try:
                messenger.log_status(TaskStatus.RUNNING, "Creating services.")
                task_model, function_finder = self.create_services(config, messenger)
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
                task_graph = TaskGraph(task_model, messenger, function_finder, config)
            except Exception as e:
                messenger.log_problem(
                    ProblemLevel.FATAL,
                    f"Failed to load the task graph: {e}",
                    traceback.format_exc(),
                )
                messenger.log_status(TaskStatus.DONE, self.fail_message)
                return

            if config.no_run:
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
            self.shut_down(config)


class DefaultScript(Script[BaseConfig]):
    def create_config(self) -> BaseConfig:
        return BaseConfig()

    def create_messenger(self, config: BaseConfig) -> Messenger:
        file_messenger = FileMessenger(Path("autochecklist.log"))
        input_messenger = (
            TkMessenger("Autochecklist", "")
            if config.ui == "tk"
            else ConsoleMessenger("", show_task_status=config.verbose)
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, config: BaseConfig, messenger: Messenger
    ) -> Tuple[Union[Path, TaskModel], FunctionFinder]:
        function_finder = FunctionFinder(module=None, arguments=[], messenger=messenger)
        return Path("tasks.json"), function_finder

    def shut_down(self, config: BaseConfig) -> None:
        pass
