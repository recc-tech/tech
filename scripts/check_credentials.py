import traceback
from argparse import ArgumentParser, Namespace
from datetime import datetime

from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    Messenger,
    ProblemLevel,
    TaskStatus,
)
from common import parse_directory
from mcr_teardown import BoxCastClientFactory, CredentialStore, ReccVimeoClient

DESCRIPTION = "This script will test the credentials for various services we connect to and ask the user to enter any missing or incorrect ones if necessary."


def main():
    args = _parse_args()

    log_dir = args.home_dir.joinpath("Logs")
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_dir.joinpath(f"{date_ymd} {current_time} check_credentials.log")
    file_messenger = FileMessenger(log_file=log_file)
    console_messenger = ConsoleMessenger(description=DESCRIPTION)
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=console_messenger
    )

    should_messenger_finish = True
    try:
        credential_store = CredentialStore(
            messenger=messenger, force_user_input=args.force_input
        )

        ReccVimeoClient(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
            # Since lazy_login = false, the login should be tested eagerly
            lazy_login=False,
        )

        BoxCastClientFactory(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
            headless=not args.show_browser,
            # Since lazy_login = false, the login should be tested eagerly
            lazy_login=False,
            log_directory=log_dir,
            log_file_name="check_credentials_web_driver",
        )

        messenger.log_status(TaskStatus.DONE, "Everything looks good!")
    except KeyboardInterrupt:
        print("\nProgram cancelled.")
        should_messenger_finish = False
    except BaseException as e:
        messenger.log_problem(
            ProblemLevel.FATAL,
            f"An error occurred: {e}",
            stacktrace=traceback.format_exc(),
        )
        messenger.log_status(
            TaskStatus.DONE, "Program finished unsuccessfully. Please try again."
        )
    finally:
        messenger.close(wait=should_messenger_finish)


def _parse_args() -> Namespace:
    parser = ArgumentParser(description=DESCRIPTION)

    advanced_args = parser.add_argument_group("Advanced arguments")
    advanced_args.add_argument(
        "--force-input",
        action="store_true",
        help="If this flag is provided, then the user will be asked to enter all credentials regardless of whether they have previously been stored.",
    )
    advanced_args.add_argument(
        "--home-dir",
        type=parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
    )
    advanced_args.add_argument(
        "--show-browser",
        action="store_true",
        help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()
