from __future__ import annotations

import logging
import re
import traceback
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from pathlib import Path

from boxcast_client import BoxCastClientFactory
from config import Config
from credentials import get_credential
from messenger import ConsoleMessenger, FileMessenger, Messenger
from task import FunctionFinder, TaskGraph
from vimeo import VimeoClient  # type: ignore
import mcr_teardown.tasks

# TODO: Create a `MockBoxCastClient` for testing. Override all methods (set them to None? https://docs.python.org/3/library/exceptions.html#NotImplementedError) to prevent unintentionally doing things for real. Have `get()` just retrieve a corresponding HTML file. Have `click()`, `clear()`, `send_keys()`, etc. just record the fact that the click/input happened.
# TODO: Also let user specify priority (e.g., so manual tasks are done first?)
# TODO: Split MCR teardown checklist into manual and automated tasks. In the automated tasks section, add a reminder that, if someone changes the checklist, they should also create an issue to update the script (ideally make the change in the manual section at first?) Alternatively, add the manual tasks to the script and go directly to the "fallback" message.
# TODO: Save progress in a file in case the script needs to be stopped and restarted? It would probably be nice to create one or more classes to encapsulate this. Watch out for race conditions if only one class is used (maybe better to have one class per thread).
# TODO: Make it easier to kill the program
# TODO: Let tasks optionally include a verifier method that checks whether the step was completed properly
# TODO: Visualize task graph?
# TODO: Use ANSI escape sequences to move the cursor around, show status of all threads. Or would it be better to use the terminal only for input and output current status of each thread in a file?
# TODO: Make Messenger methods static so I can access them from anywhere without needing to pass the object around?
# TODO: Close down Messenger properly in the event of an exception
# TODO: Make console output coloured to better highlight warnings?


def main():
    args = _parse_args()

    config = Config(
        home_dir=args.home_dir,
        message_series=args.message_series,
        message_title=args.message_title,
        boxcast_event_id=args.boxcast_event_id,
    )

    messenger = _create_messenger(config.log_dir)

    vimeo_client = _create_vimeo_client(messenger)

    boxcast_client_factory = BoxCastClientFactory(messenger)

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
        messenger.log(logging.INFO, "Successfully loaded the task graph.")
    except Exception as e:
        messenger.log_separate(
            logging.FATAL,
            f"Failed to load task graph: {e}",
            f"Failed to load task graph:\n{traceback.format_exc()}",
        )
        messenger.close()
        return

    try:
        if args.no_run:
            messenger.close()
        else:
            task_graph.run()
            messenger.close()
            print("\nGreat work :)\n")
    except Exception as e:
        messenger.log_separate(
            logging.FATAL,
            f"Failed to run task graph: {e}",
            f"Failed to run task graph: {traceback.format_exc()}",
        )
        messenger.close()


def _create_messenger(log_directory: Path) -> Messenger:
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_directory.joinpath(f"{current_date} {current_time} mcr_teardown.log")
    file_messenger = FileMessenger(log_file)

    console_messenger = ConsoleMessenger()

    return Messenger(file_messenger=file_messenger, console_messenger=console_messenger)


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
                logging.DEBUG, f"Vimeo client is able to access GET /tutorial endpoint."
            )
            return client
        else:
            messenger.log(
                logging.ERROR,
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
    parser.add_argument(
        "-d",
        "--home-dir",
        type=_parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="Home directory.",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
    )
    parser.add_argument(
        "--no-auto",
        action="store_true",
        help="If this flag is provided, no tasks will be completed automatically - user input will be required for each one.",
    )

    boxcast_event_id_group = parser.add_mutually_exclusive_group(required=True)
    boxcast_event_id_group.add_argument(
        "-b",
        "--boxcast-event-url",
        help="URL of the event in BoxCast. For example, https://dashboard.boxcast.com/#/events/abcdefghijklm0123456.",
    )
    boxcast_event_id_group.add_argument(
        "--boxcast-event-id",
        help='ID of the event in BoxCast. For example, in the URL https://dashboard.boxcast.com/#/events/abcdefghijklm0123456, the event ID is "abcdefghijklm0123456" (without the quotation marks).',
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
    # The event URL should be in the form "https://dashboard.boxcast.com/#/events/<EVENT-ID>"
    # Allow a trailing forward slash just in case
    event_url = event_url.strip()
    pattern = re.compile(
        "^https://dashboard\\.boxcast\\.com/#/events/([a-zA-Z0-9]+)/?$"
    )
    regex_match = pattern.search(event_url)
    if not regex_match:
        raise ValueError(
            f"Expected the BoxCast event URL to be in the form 'https://dashboard.boxcast.com/#/events/<EVENT-ID>', but received '{event_url}'."
        )
    event_id = regex_match.group(1)
    if len(event_id) != 20:
        raise ValueError(
            f"Expected the BoxCast event ID to be 20 characters long, but '{event_id}' has a length of {len(event_id)} characters. Are you sure you copied the entire URL?"
        )
    return event_id


if __name__ == "__main__":
    main()
