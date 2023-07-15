from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from pathlib import Path

from autochecklist.messenger import ConsoleMessenger, FileMessenger, Messenger
from mcr_teardown import BoxCastClientFactory, CredentialStore, ReccVimeoClient


def main():
    args = _parse_args()

    log_dir = args.home_dir.joinpath("Logs")
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_dir.joinpath(f"{date_ymd} {current_time} credentials.log")
    file_messenger = FileMessenger(log_file=log_file)
    console_messenger = ConsoleMessenger(
        description="This script will test the credentials for various services we connect to. You will be asked to enter any missing or incorrect ones if necessary."
    )
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=console_messenger
    )
    credential_store = CredentialStore(messenger=messenger, force_user_input=args.force_input)

    _check_mcr_teardown_credentials(
        messenger=messenger,
        credential_store=credential_store,
        headless=not args.show_browser,
    )

    messenger.close()
    print()
    print("Everything looks good!")
    print()


def _check_mcr_teardown_credentials(
    messenger: Messenger, credential_store: CredentialStore, headless: bool
):
    ReccVimeoClient(
        messenger=messenger,
        credential_store=credential_store,
        lazy_login=False,
    )

    BoxCastClientFactory(
        messenger=messenger,
        credential_store=credential_store,
        headless=headless,
        lazy_login=False,
    )


def _parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Script to test credentials and get or correct them if necessary."
    )

    parser.add_argument(
        "--force-input",
        action="store_true",
        help="If this flag is provided, then the user will be asked to enter all credentials regardless of whether they have previously been stored.",
    )
    parser.add_argument(
        "--home-dir",
        type=_parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
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
