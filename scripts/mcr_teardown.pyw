from __future__ import annotations

import logging
import re
import traceback
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

import mcr_teardown.tasks
from autochecklist import (
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
)
from common import (
    CredentialStore,
    Plan,
    PlanningCenterClient,
    parse_directory,
    parse_non_empty_string,
    run_with_or_without_terminal,
)
from mcr_teardown import BoxCastClientFactory, McrTeardownConfig, ReccVimeoClient

_DESCRIPTION = "This script will guide you through the steps to shutting down the MCR video station after a Sunday gathering."


def main():
    args = _parse_command_line_args()

    config = McrTeardownConfig(
        home_dir=args.home_dir,
        downloads_dir=args.downloads_dir,
        now=(datetime.combine(args.date, datetime.now().time()) if args.date else None),
    )

    file_messenger = FileMessenger(config.log_file)
    input_messenger = (
        ConsoleMessenger(
            f"{_DESCRIPTION}\n\nIf you need to stop the script, press CTRL+C or close the terminal window.",
            log_level=logging.INFO if args.verbose else logging.WARN,
        )
        if args.text_ui
        else TkMessenger(
            title="MCR Teardown",
            description=_DESCRIPTION,
        )
    )
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=input_messenger
    )

    should_messenger_finish = True
    try:
        try:
            messenger.log_status(TaskStatus.RUNNING, "Starting the script...")

            credential_store = CredentialStore(messenger=messenger)

            try:
                planning_center_client = PlanningCenterClient(
                    messenger=messenger,
                    credential_store=credential_store,
                    lazy_login=args.lazy_login,
                )
            except:
                messenger.log_problem(
                    ProblemLevel.WARN,
                    "Failed to connect to the Planning Center API.",
                    stacktrace=traceback.format_exc(),
                )
                planning_center_client = None

            args = _get_missing_args(
                args,
                messenger,
                planning_center_client,
                today=args.date if args.date else date.today(),
            )
            config.message_series = args.message_series
            config.message_title = args.message_title
            config.boxcast_event_id = args.boxcast_event_id

            vimeo_client = ReccVimeoClient(
                messenger=messenger,
                credential_store=credential_store,
                cancellation_token=None,
                lazy_login=args.lazy_login,
            )

            boxcast_client_factory = BoxCastClientFactory(
                messenger=messenger,
                credential_store=credential_store,
                cancellation_token=None,
                headless=not args.show_browser,
                lazy_login=args.lazy_login,
                log_directory=config.log_dir,
                log_file_name="mcr_teardown_web_driver",
            )

            function_finder = FunctionFinder(
                module=None if args.no_auto else mcr_teardown.tasks,
                arguments=[boxcast_client_factory, config, messenger, vimeo_client],
                messenger=messenger,
            )

            task_list_file = (
                Path(__file__).parent.joinpath("mcr_teardown").joinpath("tasks.json")
            )
            messenger.log_status(
                TaskStatus.RUNNING,
                f"Loading the task graph from {task_list_file.as_posix()}...",
            )
            task_model = TaskModel.load(task_list_file)
            task_graph = TaskGraph(task_model, messenger, function_finder, config)
            messenger.log_status(
                TaskStatus.RUNNING, "Successfully loaded the task graph."
            )
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.FATAL,
                f"Failed to load the task graph: {e}",
                stacktrace=traceback.format_exc(),
            )
            messenger.log_status(TaskStatus.DONE, "The script failed to start.")
            return

        try:
            if not args.no_run:
                messenger.log_status(TaskStatus.RUNNING, "Running tasks.")
                task_graph.run()
                messenger.log_status(
                    TaskStatus.DONE, "All tasks are done! Great work :)"
                )
            else:
                messenger.log_status(
                    TaskStatus.DONE,
                    "No tasks were run because the --no-run flag was given.",
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


def _parse_command_line_args() -> Namespace:
    parser = ArgumentParser(
        description="Script to guide and automate the teardown process in the MCR."
    )

    parser.add_argument(
        "-s",
        "--message-series",
        type=parse_non_empty_string,
        help="Name of the series to which today's sermon belongs.",
    )
    parser.add_argument(
        "-t",
        "--message-title",
        type=parse_non_empty_string,
        help="Title of today's sermon.",
    )

    boxcast_event_id_group = parser.add_mutually_exclusive_group()
    boxcast_event_id_group.add_argument(
        "-b",
        "--boxcast-event-url",
        type=_parse_boxcast_event_url,
        help="URL of today's live event on BoxCast. For example, https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456.",
    )
    boxcast_event_id_group.add_argument(
        "--boxcast-event-id",
        type=parse_non_empty_string,
        help='ID of today\'s live event on BoxCast. For example, in the URL https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456, the event ID is "abcdefghijklm0123456" (without the quotation marks).',
    )

    advanced_args = parser.add_argument_group("Advanced arguments")
    advanced_args.add_argument(
        "--home-dir",
        type=parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
    )
    advanced_args.add_argument(
        "--downloads-dir",
        type=parse_directory,
        default="D:\\Users\\Tech\\Downloads",
        help="The downloads directory, where the browser automatically places files after downloading them.",
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
    advanced_args.add_argument(
        "--lazy-login",
        action="store_true",
        help="If this flag is provided, then the script will not immediately log in to services like Vimeo and BoxCast. Instead, it will wait until that particular service is specifically requested.",
    )

    debug_args = parser.add_argument_group("Debug arguments")
    debug_args.add_argument(
        "--no-run",
        action="store_true",
        help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
    )
    debug_args.add_argument(
        "--no-auto",
        action="store_true",
        help="If this flag is provided, no tasks will be completed automatically - user input will be required for each one.",
    )
    debug_args.add_argument(
        "--show-browser",
        action="store_true",
        help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
    )
    debug_args.add_argument(
        "--date",
        type=lambda x: datetime.strptime(x, "%Y-%m-%d").date(),
        help="Pretend the script is running on a different date.",
    )

    args = parser.parse_args()
    if args.boxcast_event_url:
        args.boxcast_event_id = args.boxcast_event_url
    # For some reason Pylance complains about the del keyword but not delattr
    delattr(args, "boxcast_event_url")
    if args.verbose and not args.text_ui:
        parser.error(
            "The --verbose flag is only applicable when the --text-ui flag is also provided."
        )

    return args


def _get_missing_args(
    cmd_args: Namespace,
    messenger: Messenger,
    planning_center_client: Optional[PlanningCenterClient],
    today: date,
) -> Namespace:
    params: Dict[str, Parameter] = {}
    todays_plan: Optional[Plan] = None
    if planning_center_client and not (
        cmd_args.message_series and cmd_args.message_title
    ):
        try:
            todays_plan = planning_center_client.find_plan_by_date(today)
        except:
            messenger.log_problem(
                ProblemLevel.WARN,
                "Failed to fetch today's plan from Planning Center.",
                stacktrace=traceback.format_exc(),
            )
    if not cmd_args.message_series:
        params["message_series"] = Parameter(
            "Message Series",
            parser=parse_non_empty_string,
            description='This is the name of the series to which today\'s sermon belongs. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the series was "Getting There".',
            default="" if not todays_plan else todays_plan.series_title,
        )
    if not cmd_args.message_title:
        params["message_title"] = Parameter(
            "Message Title",
            parser=parse_non_empty_string,
            description='This is the title of today\'s sermon. For example, on July 23, 2023 (https://services.planningcenteronline.com/plans/65898313), the title was "Avoiding Road Rage".',
            default="" if not todays_plan else todays_plan.title,
        )
    if not cmd_args.boxcast_event_id:
        params["boxcast_event_id"] = Parameter(
            "BoxCast Event URL",
            parser=_parse_boxcast_event_url,
            description="This is the URL of today's live event on BoxCast. For example, https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456.",
        )

    if len(params) == 0:
        return cmd_args

    user_args = messenger.input_multiple(
        params, prompt="The script needs some more information to get started."
    )
    if "message_series" in user_args:
        cmd_args.message_series = user_args["message_series"]
    if "message_title" in user_args:
        cmd_args.message_title = user_args["message_title"]
    if "boxcast_event_id" in user_args:
        cmd_args.boxcast_event_id = user_args["boxcast_event_id"]

    return cmd_args


def _parse_boxcast_event_url(event_url: str) -> str:
    if not event_url:
        raise ArgumentTypeError("Empty input. The event URL is required.")
    if all(c == "\x16" for c in event_url):
        # TODO: Make this same check everywhere? Write a custom input() function that adds this check?
        raise ArgumentTypeError(
            "You entered the value CTRL+V, which is not a valid event URL. Try right-clicking to paste."
        )

    # The event URL should be in the form "https://dashboard.boxcast.com/broadcasts/<EVENT-ID>"
    # Allow a trailing forward slash just in case
    event_url = event_url.strip()
    regex = "^https://dashboard\\.boxcast\\.com/broadcasts/([a-zA-Z0-9]{20,20})/?(?:\\?.*)?$"
    pattern = re.compile(regex)
    regex_match = pattern.search(event_url)
    if not regex_match:
        raise ArgumentTypeError(
            f"Expected the BoxCast event URL to match the regular expression '{regex}', but received '{event_url}'. Are you sure you copied the URL correctly? If you think there is a problem with the script, try entering the BoxCast event ID directly instead."
        )
    event_id = regex_match.group(1)
    return event_id


if __name__ == "__main__":
    run_with_or_without_terminal(
        main, error_file=Path(__file__).parent.joinpath("error.log")
    )
