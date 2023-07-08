from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from enum import Enum
from pathlib import Path

import keyring
from autochecklist.messenger import ConsoleMessenger, FileMessenger, Messenger


# It's useful for testing purposes to keep a central list of passwords.
class Credential(Enum):
    BOXCAST_PASSWORD = ("boxcast_password", "BoxCast password")
    BOXCAST_USERNAME = ("boxcast_username", "BoxCast username")
    VIMEO_ACCESS_TOKEN = ("vimeo_access_token", "Vimeo access token")
    VIMEO_CLIENT_ID = ("vimeo_client_id", "Vimeo client ID")
    VIMEO_CLIENT_SECRET = ("vimeo_client_secret", "Vimeo client secret")


class CredentialStore:
    _KEYRING_APP_NAME = "recc_tech_mcr_teardown"

    def __init__(self, messenger: Messenger):
        self._messenger = messenger

    def get(
        self,
        credential: Credential,
        force_user_input: bool,
    ) -> str:
        (name, display_name) = credential.value

        if not force_user_input:
            value = keyring.get_password(CredentialStore._KEYRING_APP_NAME, name)
            if value:
                return value

        base_prompt = f"Enter {display_name}: "
        prompt = base_prompt
        while True:
            value = self._messenger.input_password(prompt)
            if not value:
                prompt = (
                    f"You just entered a blank value. Please try again. {base_prompt}"
                )
            elif value.upper() == "\x16":
                prompt = f"You just entered the value CTRL+V. Try right-clicking to paste. {base_prompt}"
            else:
                keyring.set_password(CredentialStore._KEYRING_APP_NAME, name, value)
                return value


def main():
    # TODO: Add a command-line flag to test each group of credentials? The testing might need to happen in a separate file to avoid circular dependencies
    # TODO: Let the user skip credentials (e.g., by pressing CTRL+C)?

    args = _parse_args()

    log_dir = args.home_dir.joinpath("Logs")
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_dir.joinpath(f"{date_ymd} {current_time} credentials.log")
    file_messenger = FileMessenger(log_file=log_file)

    console_messenger = ConsoleMessenger(
        description="Enter all the requested credentials."
    )

    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=console_messenger
    )
    credential_store = CredentialStore(messenger=messenger)

    for credential in Credential:
        credential_store.get(credential, force_user_input=True)


def _parse_args() -> Namespace:
    parser = ArgumentParser(description="Script to set all credentials.")

    parser.add_argument(
        "--home-dir",
        type=_parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
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
