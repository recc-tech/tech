import argparse
import random
import sys
from datetime import timedelta
from pathlib import Path
from typing import Callable, Literal, TypeVar

import autochecklist

from . import (
    BaseArgs,
    BaseConfig,
    DependencyProvider,
    ListChoice,
    Messenger,
    MessengerSettings,
    Parameter,
    ProblemLevel,
    TaskModel,
    TaskStatus,
    wait,
)

T = TypeVar("T")

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
        TaskStatus.RUNNING,
        f"You choose {inputs['pizza_topping']} on pizza and your password is '{inputs['pass']}'.",
    )

    choices = [
        ListChoice(value="id:A", display="Option A"),
        ListChoice(value="id:B", display="Option B"),
        ListChoice(value="id:C", display="Option C"),
    ]
    choice = messenger.input_from_list(
        choices,
        prompt="This is what it looks like to choose from a list of options.",
        title="Choose option",
    )
    messenger.log_status(TaskStatus.DONE, f"You choose the option with value {choice}.")


def demo_errors(messenger: Messenger) -> None:
    messenger.log_problem(ProblemLevel.WARN, "This is what a warning looks like.")
    messenger.log_problem(
        ProblemLevel.ERROR,
        "This is what an error looks like."
        " Maybe you'd like to link to [[url|https://xkcd.com/627/|a troubleshooting page]].",
    )
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
            wait.sleep_attentively(
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
            wait.sleep_attentively(
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
    wait.sleep_attentively(timeout=timedelta(minutes=5), cancellation_token=token)


def demo_cancel2(messenger: Messenger) -> None:
    demo_cancel1(messenger)


class DemoArgs(BaseArgs):
    def __init__(self, args: argparse.Namespace, error: Callable[[str], None]) -> None:
        self.ui_theme: Literal["dark", "light"] = args.theme
        super().__init__(args, error)

    @classmethod
    def set_up_parser(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--theme",
            choices={"dark", "light"},
            default="dark",
            help="User interface theme (light or dark).",
        )
        return super().set_up_parser(parser)


if __name__ == "__main__":
    args = DemoArgs.parse(sys.argv)
    config = BaseConfig()
    tasks = TaskModel(
        name="demo",
        subtasks=[
            TaskModel(
                name="demo_manual",
                description="This is what a non-automated task looks like. It can even have hyperlinks (such as [[url|https://xkcd.com/]] or [[url|https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/418|HTTP 418]])!",
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
    msg = MessengerSettings(
        log_file=Path(__file__).parent.joinpath("demo.log"),
        script_name="AutoChecklist Demo",
        description=_DESCRIPTION,
        confirm_exit_message="Are you sure you want to exit? The script is not done yet.",
        show_statuses_by_default=True,
        ui_theme=args.ui_theme,
        icon=None,
        # No point in passing True here, since this script will always have
        # some warnings and errors if you run the whole thing
        auto_close=False,
    )
    dependency_provider = DependencyProvider(args=args, config=config, messenger=msg)
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dependency_provider,
        tasks=tasks,
        module=sys.modules[__name__],
    )
