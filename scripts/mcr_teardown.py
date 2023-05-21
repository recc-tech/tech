from __future__ import annotations

import logging
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from getpass import getpass
from pathlib import Path

import keyring
from vimeo import VimeoClient

from config import Config
from messenger import Messenger
from task import TaskGraph

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
# TODO: Add a reminder to check and close the checklist on GitHub? It would need to depend on all the previous tasks, which is a bit annoying. Can there be a built-in mechanism for this? Organize tasks into TaskGroups?


def main():
    args = _parse_args()

    config = Config(
        home_dir=args.home_dir,
        message_series=args.message_series,
        message_title=args.message_title,
    )

    messenger = _create_messenger(config.log_dir)

    vimeo_client = _create_vimeo_client(config.KEYRING_APP_NAME, messenger)

    try:
        task_file = Path(__file__).parent.joinpath("mcr_teardown_tasks.json")
        task_graph = TaskGraph.load(
            task_file=task_file,
            config=config,
            messenger=messenger,
            vimeo_client=vimeo_client,
        )
    except Exception as e:
        messenger.log(logging.FATAL, f"Failed to load task graph: {e}")
        messenger.close()
        return

    try:
        task_graph.start()
        task_graph.join()
    except Exception as e:
        messenger.log(logging.FATAL, f"Failed to run task graph: {e}")
    finally:
        messenger.close()


def _create_messenger(log_directory: Path) -> Messenger:
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_directory.joinpath(f"{current_date} {current_time} mcr_teardown.log")
    return Messenger(log_file)


def _create_vimeo_client(app_name: str, messenger: Messenger) -> VimeoClient:
    first_attempt = True

    while True:
        token = _get_credential(
            app_name,
            "vimeo_access_token",
            "Vimeo access token",
            force_user_input=not first_attempt,
        )
        client_id = _get_credential(
            app_name,
            "vimeo_client_id",
            "Vimeo client ID",
            force_user_input=not first_attempt,
        )
        client_secret = _get_credential(
            app_name,
            "vimeo_client_secret",
            "Vimeo client secret",
            force_user_input=not first_attempt,
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
                logging.WARN,
                f"Vimeo client test request failed (HTTP status {response.status_code}).",
            )
            first_attempt = False
            # TODO: Give the user the option to decide whether or not they want to try again If they don't, return None
            # instead and have every step that requires the Vimeo client request user intervention.


def _get_credential(
    app_name: str,
    credential_username: str,
    credential_display_name: str,
    force_user_input: bool = False,
) -> str:
    if not force_user_input:
        value = keyring.get_password(app_name, credential_username)
        if value:
            return value

    while True:
        value = getpass(f"Enter {credential_display_name}: ")
        if not value:
            print("You just entered a blank value. Please try again.")
        elif value.upper() == "^V":
            print("You just entered the value '^V'. Try right-clicking to paste.")
        else:
            break

    keyring.set_password(app_name, credential_username, value)
    return value


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
    )

    return parser.parse_args()


def _parse_directory(path_str: str) -> Path:
    path = Path(path_str)

    if not path.exists():
        raise ArgumentTypeError(f"Path '{path_str}' does not exist.")
    if not path.is_dir():
        raise ArgumentTypeError(f"Path '{path_str}' is not a directory.")
    # TODO: Check whether the path is accessible?

    path = path.resolve()
    return path


if __name__ == "__main__":
    main()