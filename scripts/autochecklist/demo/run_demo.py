import argparse
import random
import sys
from datetime import timedelta
from pathlib import Path
from typing import Tuple, TypeVar

T = TypeVar("T")

from .. import (
    BaseConfig,
    ConsoleMessenger,
    DefaultScript,
    EelMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Parameter,
    ProblemLevel,
    TaskModel,
    TaskStatus,
    TkMessenger,
    sleep_attentively,
)

_DESCRIPTION = "This is a demo of the autochecklist package."


def demo_input(messenger: Messenger) -> None:
    def require_number(x: str) -> str:
        if all([not c.isnumeric() for c in x]):
            raise argparse.ArgumentTypeError("At least one digit is required.")
        return x

    username = messenger.input(
        display_name="Favourite Number",
        password=False,
        parser=int,
        prompt="Enter your favourite number.",
        title="Choose number",
    )
    messenger.log_status(TaskStatus.RUNNING, f"Your favourite number: {username}")

    def parse_pizza_topping(x: str) -> str:
        if x.lower() != "pineapple":
            raise argparse.ArgumentTypeError(
                "Wrong choice (hint: the right choice starts with 'p' and ends with 'ineapple')."
            )
        return x

    inputs = messenger.input_multiple(
        params={
            "pizza_topping": Parameter(
                display_name="Pizza topping",
                parser=parse_pizza_topping,
                password=False,
                description="What is your favourite pizza topping? There is exactly one right answer.",
                default="pineapple",
            ),
            "pass": Parameter(
                display_name="Password",
                password=True,
                parser=require_number,
                description="Make up a password (DON'T use a real one since it will be displayed and logged!). It must contain at least one digit.",
            ),
        },
        prompt="This is what it looks like to take multiple inputs at once.",
        title="Choose multiple",
    )
    messenger.log_status(
        TaskStatus.DONE,
        f"You choose {inputs['pizza_topping']} on pizza and your password is '{inputs['pass']}'.",
    )


def demo_errors(messenger: Messenger) -> None:
    messenger.log_problem(ProblemLevel.WARN, "This is what a warning looks like.")
    messenger.log_problem(ProblemLevel.ERROR, "This is what an error looks like.")
    messenger.log_problem(ProblemLevel.FATAL, "This is what a fatal error looks like.")
    raise ValueError("This is what happens when a task throws an exception.")


def demo_progress1(messenger: Messenger) -> None:
    job1_max = 42
    job1_progress = 0
    job2_max = 100
    job2_progress = 0
    cancellation_token = messenger.allow_cancel()
    job1_key = messenger.create_progress_bar(display_name="Job 1.1", max_value=job1_max)
    job2_key = messenger.create_progress_bar(display_name="Job 1.2", max_value=job2_max)
    try:
        messenger.log_status(TaskStatus.RUNNING, "Showing progress bars.")
        while job1_progress < job1_max or job2_progress < job2_max:
            sleep_attentively(
                timeout=timedelta(seconds=1), cancellation_token=cancellation_token
            )
            if job1_progress < job1_max:
                job1_progress += random.uniform(job1_max / 4, job1_max / 2)
                messenger.update_progress_bar(job1_key, job1_progress)
            if job2_progress < job2_max:
                job2_progress += random.uniform(job2_max / 6, job2_max / 4)
                messenger.update_progress_bar(job2_key, job2_progress)
    finally:
        messenger.delete_progress_bar(job1_key)
        messenger.delete_progress_bar(job2_key)


def demo_progress2(messenger: Messenger) -> None:
    job1_max = 42
    job1_progress = 0
    job2_max = 100
    job2_progress = 0
    cancellation_token = messenger.allow_cancel()
    job1_key = messenger.create_progress_bar(display_name="Job 2.1", max_value=job1_max)
    job2_key = messenger.create_progress_bar(display_name="Job 2.2", max_value=job2_max)
    try:
        messenger.log_status(TaskStatus.RUNNING, "Showing progress bars.")
        while job1_progress < job1_max or job2_progress < job2_max:
            sleep_attentively(
                timeout=timedelta(seconds=1), cancellation_token=cancellation_token
            )
            if job1_progress < job1_max:
                job1_progress += random.uniform(job1_max / 8, job1_max / 6)
                messenger.update_progress_bar(job1_key, job1_progress)
            if job2_progress < job2_max:
                job2_progress += random.uniform(job2_max / 10, job2_max / 8)
                messenger.update_progress_bar(job2_key, job2_progress)
    finally:
        messenger.delete_progress_bar(job1_key)
        messenger.delete_progress_bar(job2_key)


def demo_cancel1(messenger: Messenger) -> None:
    messenger.log_status(
        TaskStatus.RUNNING,
        "This task will run for a long time. Furthermore, it cannot be done manually. Try cancelling it.",
    )
    token = messenger.allow_cancel()
    sleep_attentively(timeout=timedelta(minutes=5), cancellation_token=token)


def demo_cancel2(messenger: Messenger) -> None:
    demo_cancel1(messenger)


class DemoScript(DefaultScript):
    def create_config(self) -> BaseConfig:
        parser = argparse.ArgumentParser(description=_DESCRIPTION)
        parser.add_argument(
            "--ui",
            choices=["console", "tk", "eel"],
            default="tk",
            help="User interface to use.",
        )
        debug_args = parser.add_argument_group("Debug arguments")
        debug_args.add_argument(
            "--verbose",
            action="store_true",
            help="This flag is only applicable when the console UI is used. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
        )
        debug_args.add_argument(
            "--no-run",
            action="store_true",
            help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
        )
        args = parser.parse_args()
        return BaseConfig(ui=args.ui, verbose=args.verbose, no_run=args.no_run)

    def create_messenger(self, config: BaseConfig) -> Messenger:
        file_messenger = FileMessenger(
            log_file=Path(__file__).parent.joinpath("demo.log")
        )
        input_messenger = (
            ConsoleMessenger(description=_DESCRIPTION, show_task_status=config.verbose)
            if config.ui == "console"
            else TkMessenger(title="autochecklist demo", description=_DESCRIPTION)
            if config.ui == "tk"
            else EelMessenger(title="autochecklist demo", description=_DESCRIPTION)
        )
        messenger = Messenger(
            file_messenger=file_messenger, input_messenger=input_messenger
        )
        return messenger

    def create_services(
        self, config: BaseConfig, messenger: Messenger
    ) -> Tuple[TaskModel, FunctionFinder]:
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[messenger],
            messenger=messenger,
        )
        task_model = TaskModel(
            name="demo",
            subtasks=[
                TaskModel(
                    name="demo_manual",
                    description="This is what a non-automated task looks like.",
                ),
                TaskModel(
                    name="demo_input",
                    description="This task will ask for various kinds of input.",
                    prerequisites={"demo_manual"},
                ),
                TaskModel(
                    name="demo_errors",
                    description="This task will always fail. Try retrying it once or twice, then press 'Done.'",
                    prerequisites={"demo_input"},
                ),
                TaskModel(
                    name="demo_progress",
                    prerequisites={"demo_errors"},
                    subtasks=[
                        TaskModel(
                            name="demo_progress1",
                            description="This task will show a few progress bars. It cannot be done manually.",
                            only_auto=True,
                        ),
                        TaskModel(
                            name="demo_progress2",
                            description="This task will show a few progress bars. It cannot be done manually.",
                            only_auto=True,
                        ),
                    ],
                ),
                TaskModel(
                    name="demo_cancel",
                    prerequisites={"demo_progress"},
                    subtasks=[
                        TaskModel(
                            name="demo_cancel1",
                            description="This task will run for a long time. It cannot be done manually.",
                            only_auto=True,
                        ),
                        TaskModel(
                            name="demo_cancel2",
                            description="This task will run for a long time. It cannot be done manually.",
                            only_auto=True,
                        ),
                    ],
                ),
            ],
        )
        return task_model, function_finder


def main():
    DemoScript().run()


if __name__ == "__main__":
    main()
