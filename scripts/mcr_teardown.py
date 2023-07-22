from __future__ import annotations

import re
import traceback
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path

import mcr_teardown.tasks
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    ProblemLevel,
    TaskGraph,
    TaskStatus,
    TkMessenger,
    set_current_task_name,
)
from mcr_teardown import (
    BoxCastClientFactory,
    CredentialStore,
    McrTeardownConfig,
    ReccVimeoClient,
)
from parsing_helpers import parse_directory, parse_non_empty_string

# TODO: Test the BoxCast code by turning off the WiFi after loading the page.
# TODO: Save progress in a file in case the script needs to be stopped and restarted?

DESCRIPTION = "This script will guide you through the steps to shutting down the MCR video station. It is based on the checklist on GitHub (see https://github.com/recc-tech/tech/issues)."


def main():
    args = _parse_args()

    set_current_task_name("SCRIPT MAIN")

    config = McrTeardownConfig(
        home_dir=args.home_dir,
        downloads_dir=args.downloads_dir,
        message_series=args.message_series,
        message_title=args.message_title,
        boxcast_event_id=args.boxcast_event_id,
    )

    file_messenger = FileMessenger(config.log_file)
    extended_description = f"{DESCRIPTION}\n\nIf you need to debug the program, see the log file at {config.log_file.resolve().as_posix()}."
    input_messenger = (
        ConsoleMessenger(
            f"{extended_description}\n\nIf you need to stop the script, press CTRL+C or close the terminal window."
        )
        if args.text_ui
        else TkMessenger(
            f"{extended_description}\n\nIf you need to stop the script, close this window or the terminal window."
        )
    )
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=input_messenger
    )

    messenger.log_status(TaskStatus.RUNNING, "Loading the script...")

    credential_store = CredentialStore(messenger=messenger)

    vimeo_client = ReccVimeoClient(
        messenger=messenger,
        credential_store=credential_store,
        lazy_login=args.lazy_login,
    )

    boxcast_client_factory = BoxCastClientFactory(
        messenger=messenger,
        credential_store=credential_store,
        headless=not args.show_browser,
        lazy_login=args.lazy_login,
    )

    function_finder = FunctionFinder(
        module=None if args.no_auto else mcr_teardown.tasks,
        arguments={boxcast_client_factory, config, messenger, vimeo_client},
        messenger=messenger,
    )

    try:
        task_list_file = (
            Path(__file__).parent.joinpath("mcr_teardown").joinpath("tasks.json")
        )
        messenger.log_status(
            TaskStatus.RUNNING,
            f"Loading the task graph from {task_list_file.as_posix()}...",
        )
        task_graph = TaskGraph.load(task_list_file, function_finder, messenger, config)
        messenger.log_status(TaskStatus.RUNNING, "Successfully loaded the task graph.")
    except Exception as e:
        messenger.log_problem(
            ProblemLevel.FATAL,
            f"Failed to load the task graph: {e}.",
            stacktrace=traceback.format_exc(),
        )
        messenger.log_status(TaskStatus.DONE, "The script failed to start.")
        messenger.close()
        return

    try:
        if not args.no_run:
            messenger.log_status(TaskStatus.RUNNING, "Running tasks.")
            task_graph.run()
            messenger.log_status(TaskStatus.DONE, "All tasks are done! Great work :)")
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
    except KeyboardInterrupt as e:
        messenger.log_status(TaskStatus.DONE, "The script was cancelled by the user.")
    finally:
        # TODO: Shut down the task threads more gracefully (or at least give them the chance, if they're checking)?
        messenger.close()


def _parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Script to guide and automate the teardown process in the MCR."
    )

    # TODO: Check whether the values are the same as in the previous week?
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
        "--no-run",
        action="store_true",
        help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
    )
    advanced_args.add_argument(
        "--no-auto",
        action="store_true",
        help="If this flag is provided, no tasks will be completed automatically - user input will be required for each one.",
    )
    advanced_args.add_argument(
        "--show-browser",
        action="store_true",
        help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
    )
    advanced_args.add_argument(
        "--text-ui",
        action="store_true",
        help="If this flag is provided, then user interactions will be performed via a simpler terminal-based UI.",
    )
    advanced_args.add_argument(
        "--lazy-login",
        action="store_true",
        help="If this flag is provided, then the script will not immediately log in to services like Vimeo and BoxCast. Instead, it will wait until that particular service is specifically requested.",
    )

    args = parser.parse_args()

    # TODO: Add this to the UI?
    if not args.message_series:
        args.message_series = _get_message_series()

    if not args.message_title:
        args.message_title = _get_message_title()

    if not args.boxcast_event_url and not args.boxcast_event_id:
        args.boxcast_event_id = _get_boxcast_event_id()
    elif args.boxcast_event_url:
        args.boxcast_event_id = args.boxcast_event_url
    # For some reason Pylance complains about the del keyword but not delattr
    delattr(args, "boxcast_event_url")

    return args


def _get_message_series():
    while True:
        raw_input = input("Enter the series to which today's message belongs:\n> ")
        try:
            output = parse_non_empty_string(raw_input)
            print()
            return output
        except ArgumentTypeError as e:
            print(e)


def _get_message_title():
    while True:
        raw_input = input("Enter the title of today's message:\n> ")
        try:
            output = parse_non_empty_string(raw_input)
            print()
            return output
        except ArgumentTypeError as e:
            print(e)


def _get_boxcast_event_id():
    while True:
        raw_input = input("Enter the URL of today's live event on BoxCast:\n> ")
        try:
            output = _parse_boxcast_event_url(raw_input)
            print()
            return output
        except ArgumentTypeError as e:
            print(e)


def _parse_boxcast_event_url(event_url: str) -> str:
    if event_url == "\x16":
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
    main()
