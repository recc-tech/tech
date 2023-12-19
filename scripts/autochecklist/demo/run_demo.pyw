import argparse
import sys
from datetime import timedelta
from pathlib import Path

from .. import (  # EelMessenger,
    BaseConfig,
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Parameter,
    ProblemLevel,
    TaskGraph,
    TaskModel,
    TaskStatus,
    TkMessenger,
    sleep_attentively,
)

_DESCRIPTION = "This is a demo of the autochecklist package."


def demo_input(messenger: Messenger):
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

    sleep_attentively(
        timeout=timedelta(seconds=10), cancellation_token=messenger.allow_cancel()
    )


def demo_errors(messenger: Messenger):
    messenger.log_problem(ProblemLevel.WARN, "This is what a warning looks like.")
    messenger.log_problem(ProblemLevel.ERROR, "This is what an error looks like.")
    messenger.log_problem(ProblemLevel.FATAL, "This is what a fatal error looks like.")
    raise ValueError("This is what happens when a task throws an exception.")


def demo_cancel1(messenger: Messenger):
    messenger.log_status(
        TaskStatus.RUNNING, "This task will run for a long time. Try cancelling it."
    )
    token = messenger.allow_cancel()
    sleep_attentively(timeout=timedelta(minutes=5), cancellation_token=token)


def demo_cancel2(messenger: Messenger):
    demo_cancel1(messenger)


def _main():
    args = _parse_args()
    messenger = _create_messenger(args)
    messenger.start(after_start=lambda: _run_script(args, messenger))


def _run_script(args: argparse.Namespace, messenger: Messenger) -> None:
    try:
        messenger.log_status(TaskStatus.RUNNING, "Running demo.")
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[messenger],
            messenger=messenger,
        )
        config = BaseConfig()

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
                    name="demo_cancel1",
                    description="This task will run for a long time. Try cancelling it.",
                    prerequisites={"demo_errors"},
                ),
                TaskModel(
                    name="demo_cancel2",
                    description="This task will run for a long time. Try cancelling it.",
                    prerequisites={"demo_errors"},
                ),
            ],
        )
        # The ConsoleMessenger doesn't support cancelling tasks, so skip that one
        if args.ui == "console":
            task_model = TaskModel(
                name=task_model.name,
                subtasks=[t for t in task_model.subtasks if t.name != "demo_cancel"],
            )
        task_graph = TaskGraph(task_model, messenger, function_finder, config)
        task_graph.run()
        messenger.log_status(TaskStatus.DONE, "Demo complete.")
    finally:
        messenger.close()


def _create_messenger(args: argparse.Namespace) -> Messenger:
    file_messenger = FileMessenger(log_file=Path(__file__).parent.joinpath("demo.log"))
    input_messenger = (
        ConsoleMessenger(description=_DESCRIPTION)
        if args.ui == "console"
        else TkMessenger(title="autochecklist demo", description=_DESCRIPTION)
        # if args.ui == "tk"
        # else EelMessenger(title="autochecklist demo", description=_DESCRIPTION)
    )
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=input_messenger
    )
    return messenger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=_DESCRIPTION)
    parser.add_argument(
        "ui", choices=["console", "tk", "eel"], help="UI to use for the demo."
    )
    return parser.parse_args()


if __name__ == "__main__":
    _main()
