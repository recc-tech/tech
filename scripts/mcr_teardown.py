from __future__ import annotations

import re
import traceback
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path

import mcr_teardown.tasks
from autochecklist.credentials import get_credential
from autochecklist.messenger import (ConsoleMessenger, FileMessenger, LogLevel,
                                     Messenger, TkMessenger)
from autochecklist.task import FunctionFinder, TaskGraph
from mcr_teardown.boxcast_client import BoxCastClientFactory
from mcr_teardown.config import McrTeardownConfig
from vimeo import VimeoClient  # type: ignore

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

    messenger = _create_messenger(config.log_file, args.text_ui)

    vimeo_client = _create_vimeo_client(messenger)

    boxcast_client_factory = BoxCastClientFactory(
        messenger=messenger, headless=not args.show_browser
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


def _create_messenger(log_file: Path, text_ui: bool) -> Messenger:
    file_messenger = FileMessenger(log_file)

    log_file_txt = log_file.resolve().as_posix()
    description = f"This script will guide you through the steps to shutting down the MCR video station. It is based on the checklist on GitHub (see https://github.com/recc-tech/tech/issues).\n\nIf you need to debug the program, see the log file at {log_file_txt}."
    input_messenger = (
        ConsoleMessenger(
            f"{description}\n\nPress CTRL+C at any time to stop the script."
        )
        if text_ui
        else TkMessenger(description)
    )

    return Messenger(file_messenger=file_messenger, input_messenger=input_messenger)


def _create_vimeo_client(messenger: Messenger) -> VimeoClient:
    first_attempt = True

    while True:
        token = get_credential(
            credential_username="vimeo_access_token",
            credential_display_name="Vimeo access token",
            force_user_input=not first_attempt,
            messenger=messenger,
        )
        client_id = get_credential(
            credential_username="vimeo_client_id",
            credential_display_name="Vimeo client ID",
            force_user_input=not first_attempt,
            messenger=messenger,
        )
        client_secret = get_credential(
            credential_username="vimeo_client_secret",
            credential_display_name="Vimeo client secret",
            force_user_input=not first_attempt,
            messenger=messenger,
        )

        client = VimeoClient(
            token=token,
            key=client_id,
            secret=client_secret,
        )

        # Test the client
        response = client.get("/tutorial")  # type: ignore
        if response.status_code == 200:
            messenger.log(
                _TASK_NAME,
                LogLevel.DEBUG,
                f"Vimeo client is able to access GET /tutorial endpoint.",
            )
            return client
        else:
            messenger.log(
                _TASK_NAME,
                LogLevel.ERROR,
                f"Vimeo client test request failed (HTTP status {response.status_code}).",
            )
            first_attempt = False
            # TODO: Give the user the option to decide whether or not they want to try again If they don't, return None
            # instead and have every step that requires the Vimeo client request user intervention.


def _parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Script to guide and automate the teardown process in the MCR."
    )

    # TODO: Check whether the values are the same as in the previous week?
    parser.add_argument(
        "-s",
        "--message-series",
        required=True,
        help="Name of the series to which today's sermon belongs.",
    )
    parser.add_argument(
        "-t", "--message-title", required=True, help="Title of today's sermon."
    )

    boxcast_event_id_group = parser.add_mutually_exclusive_group(required=True)
    boxcast_event_id_group.add_argument(
        "-b",
        "--boxcast-event-url",
        help="URL of the event in BoxCast. For example, https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456.",
    )
    boxcast_event_id_group.add_argument(
        "--boxcast-event-id",
        help='ID of the event in BoxCast. For example, in the URL https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456, the event ID is "abcdefghijklm0123456" (without the quotation marks).',
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

    args = parser.parse_args()

    if args.boxcast_event_url:
        args.boxcast_event_id = _parse_boxcast_event_url(args.boxcast_event_url)

    return args


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
    # The event URL should be in the form "https://dashboard.boxcast.com/broadcasts/<EVENT-ID>"
    # Allow a trailing forward slash just in case
    event_url = event_url.strip()
    regex = "^https://dashboard\\.boxcast\\.com/broadcasts/([a-zA-Z0-9]{20,20})/?(?:\\?.*)?$"
    pattern = re.compile(regex)
    regex_match = pattern.search(event_url)
    if not regex_match:
        raise ValueError(
            f"Expected the BoxCast event URL to match the regular expression '{regex}', but received '{event_url}'. Are you sure you copied the URL correctly? If you think there is a problem with the script, try entering the BoxCast event ID directly instead."
        )
    event_id = regex_match.group(1)
    return event_id


if __name__ == "__main__":
    main()
