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
    LogLevel,
    Messenger,
    TaskGraph,
    TkMessenger,
)
from mcr_teardown import (
    BoxCastClientFactory,
    CredentialStore,
    McrTeardownConfig,
    ReccVimeoClient,
)

# TODO: Create a `MockBoxCastClient` for testing. Override all methods (set them to None? https://docs.python.org/3/library/exceptions.html#NotImplementedError) to prevent unintentionally doing things for real. Have `get()` just retrieve a corresponding HTML file. Have `click()`, `clear()`, `send_keys()`, etc. just record the fact that the click/input happened.
# TODO: Also let user specify priority (e.g., so manual tasks are done first?)
# TODO: Split MCR teardown checklist into manual and automated tasks. In the automated tasks section, add a reminder that, if someone changes the checklist, they should also create an issue to update the script (ideally make the change in the manual section at first?) Alternatively, add the manual tasks to the script and go directly to the "fallback" message.
# TODO: Save progress in a file in case the script needs to be stopped and restarted? It would probably be nice to create one or more classes to encapsulate this. Watch out for race conditions if only one class is used (maybe better to have one class per thread).
# TODO: Let tasks optionally include a verifier method that checks whether the step was completed properly
# TODO: Visualize task graph?
# TODO: Use ANSI escape sequences to move the cursor around, show status of all threads. Or would it be better to use the terminal only for input and output current status of each thread in a file?
# TODO: Make Messenger methods static so I can access them from anywhere without needing to pass the object around?
# TODO: Close down Messenger properly in the event of an exception
# TODO: Make console output coloured to better highlight warnings?

_TASK_NAME = "SCRIPT MAIN"


def main():
    args = _parse_args()

    config = McrTeardownConfig(
        home_dir=args.home_dir,
        downloads_dir=args.downloads_dir,
        message_series=args.message_series,
        message_title=args.message_title,
        boxcast_event_id=args.boxcast_event_id,
    )

    file_messenger = FileMessenger(config.log_file)
    description = f"This script will guide you through the steps to shutting down the MCR video station. It is based on the checklist on GitHub (see https://github.com/recc-tech/tech/issues).\n\nIf you need to debug the program, see the log file at {config.log_file.resolve().as_posix()}."
    input_messenger = (
        ConsoleMessenger(
            f"{description}\n\nPress CTRL+C at any time to stop the script."
        )
        if args.text_ui
        else TkMessenger(description)
    )
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=input_messenger
    )

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
        task_graph = TaskGraph.load(task_list_file, function_finder, messenger, config)
        messenger.log(_TASK_NAME, LogLevel.INFO, "Successfully loaded the task graph.")
    except Exception as e:
        messenger.log_separate(
            _TASK_NAME,
            LogLevel.FATAL,
            f"Failed to load task graph: {e}",
            f"Failed to load task graph:\n{traceback.format_exc()}",
        )
        messenger.close()
        return

    success = False
    try:
        if not args.no_run:
            task_graph.run()
            success = True
    except Exception as e:
        messenger.log_separate(
            _TASK_NAME,
            LogLevel.FATAL,
            f"Failed to run task graph: {e}",
            f"Failed to run task graph:\n{traceback.format_exc()}",
        )
    except KeyboardInterrupt as e:
        messenger.log(_TASK_NAME, LogLevel.FATAL, "Program cancelled by user.")
    finally:
        # TODO: Shut down the task threads more gracefully (or at least give them the chance, if they're checking)?
        messenger.close()
        if success:
            print("\nGreat work :)\n")


def _parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Script to guide and automate the teardown process in the MCR."
    )

    # TODO: Check whether the values are the same as in the previous week?
    parser.add_argument(
        "-s",
        "--message-series",
        type=_parse_non_empty_string,
        help="Name of the series to which today's sermon belongs.",
    )
    parser.add_argument(
        "-t",
        "--message-title",
        type=_parse_non_empty_string,
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
        type=_parse_non_empty_string,
        help='ID of today\'s live event on BoxCast. For example, in the URL https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456, the event ID is "abcdefghijklm0123456" (without the quotation marks).',
    )

    advanced_args = parser.add_argument_group("Advanced arguments")
    advanced_args.add_argument(
        "--home-dir",
        type=_parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
    )
    advanced_args.add_argument(
        "--downloads-dir",
        type=_parse_directory,
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
            output = _parse_non_empty_string(raw_input)
            print()
            return output
        except ArgumentTypeError as e:
            print(e)


def _get_message_title():
    while True:
        raw_input = input("Enter the title of today's message:\n> ")
        try:
            output = _parse_non_empty_string(raw_input)
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


def _parse_non_empty_string(raw_input: str) -> str:
    if not raw_input or not raw_input.strip():
        raise ArgumentTypeError("The value cannot be empty.")
    return raw_input.strip()


def _parse_directory(path_str: str) -> Path:
    path = Path(path_str)

    if not path.exists():
        raise ArgumentTypeError(f"Path '{path_str}' does not exist.")
    if not path.is_dir():
        raise ArgumentTypeError(f"Path '{path_str}' is not a directory.")
    # TODO: Check whether the path is accessible?

    path = path.resolve()
    return path


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
