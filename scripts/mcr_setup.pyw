import logging
import traceback
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path

import mcr_setup.tasks
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    ProblemLevel,
    TaskGraph,
    TaskModel,
    TaskStatus,
    TkMessenger,
)
from common import (
    CredentialStore,
    PlanningCenterClient,
    parse_directory,
    run_with_or_without_terminal,
)
from mcr_setup.config import McrSetupConfig

_DESCRIPTION = "This script will guide you through the steps to setting up the MCR visuals station for a Sunday gathering. It is based on the checklist on GitHub (see https://github.com/recc-tech/tech/issues)."


def main():
    args = _parse_args()

    config = McrSetupConfig(
        home_dir=args.home_dir,
        now=(datetime.combine(args.date, datetime.now().time()) if args.date else None),
    )
    file_messenger = FileMessenger(log_file=config.log_file)
    input_messenger = (
        ConsoleMessenger(
            description=f"{_DESCRIPTION}\n\nIf you need to debug the program, see the log file at {config.log_file.as_posix()}.\n\nIf you need to stop the script, press CTRL+C or close the terminal window.",
            log_level=logging.INFO if args.verbose else logging.WARN,
        )
        if args.text_ui
        else TkMessenger(
            title="MCR Setup",
            description=f"{_DESCRIPTION}\n\nIf you need to debug the program, see the log file at {config.log_file.as_posix()}.\n\nIf you need to stop the script, close this window or the terminal window.",
        )
    )
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=input_messenger
    )

    should_messenger_finish = True
    try:
        credential_store = CredentialStore(messenger)
        planning_center_client = PlanningCenterClient(messenger, credential_store)
        function_finder = FunctionFinder(
            None if args.no_auto else mcr_setup.tasks,
            [planning_center_client, config, credential_store],
            messenger,
        )
        task_list_file = (
            Path(__file__).parent.joinpath("mcr_setup").joinpath("tasks.json")
        )
        messenger.log_status(
            TaskStatus.RUNNING,
            f"Loading the task graph from {task_list_file.as_posix()}...",
        )
        try:
            task_model = TaskModel.load(task_list_file)
            task_graph = TaskGraph(task_model, messenger, function_finder, config)
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to load the task graph: {e}",
                stacktrace=traceback.format_exc(),
            )
            return
        messenger.log_status(TaskStatus.RUNNING, "Successfully loaded the task graph.")

        try:
            if args.no_run:
                messenger.log_status(
                    TaskStatus.DONE,
                    "No tasks were run because the --no-run flag was given.",
                )
            else:
                messenger.log_status(TaskStatus.RUNNING, "Running tasks.")
                task_graph.run()
                messenger.log_status(
                    TaskStatus.DONE, "All tasks are done! Great work :)"
                )
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to run the tasks: {e}.",
                stacktrace=traceback.format_exc(),
            )
            messenger.log_status(TaskStatus.DONE, "The script failed.")
    except KeyboardInterrupt:
        print("\nProgram cancelled.")
        should_messenger_finish = False
    finally:
        messenger.close(wait=should_messenger_finish)


def _parse_args() -> Namespace:
    parser = ArgumentParser(description=_DESCRIPTION)

    advanced_args = parser.add_argument_group("Advanced arguments")
    advanced_args.add_argument(
        "--home-dir",
        type=parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
    )
    advanced_args.add_argument(
        "--text-ui",
        action="store_true",
        help="If this flag is provided, then user interactions will be performed via a simpler terminal-based UI.",
    )
    advanced_args.add_argument(
        "--verbose",
        action="store_true",
        help="This flag is only applicable when the flag --text-ui is also provided. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
    )

    debug_args = parser.add_argument_group("Debug arguments")
    debug_args.add_argument(
        "--no-run",
        action="store_true",
        help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
    )
    # TODO: Let the user choose *which* tasks to automate
    debug_args.add_argument(
        "--no-auto",
        action="store_true",
        help="If this flag is provided, no tasks will be completed automatically - user input will be required for each one.",
    )
    debug_args.add_argument(
        "--date",
        type=lambda x: datetime.strptime(x, "%Y-%m-%d").date(),
        help="Pretend the script is running on a different date.",
    )

    args = parser.parse_args()
    if args.verbose and not args.text_ui:
        parser.error(
            "The --verbose flag is only applicable when the --text-ui flag is also provided."
        )

    return args


if __name__ == "__main__":
    run_with_or_without_terminal(
        main, error_file=Path(__file__).parent.joinpath("error.log")
    )
