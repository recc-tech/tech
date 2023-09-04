import traceback
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path

from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    Messenger,
    ProblemLevel,
    TaskStatus,
    TkMessenger,
)
from common import Credential, CredentialStore, InputPolicy, parse_directory
from mcr_teardown import BoxCastClientFactory, ReccVimeoClient

DESCRIPTION = "This script will test the credentials for various services we connect to and ask the user to enter any missing or incorrect ones if necessary."


def main():
    args = _parse_args()

    log_dir = args.home_dir.joinpath("Logs")
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_dir.joinpath(f"{date_ymd} {current_time} check_credentials.log")
    file_messenger = FileMessenger(log_file=log_file)
    input_messenger = (
        ConsoleMessenger(description=DESCRIPTION)
        if args.text_ui
        else TkMessenger(title="Check Credentials", description=DESCRIPTION)
    )
    messenger = Messenger(
        file_messenger=file_messenger, input_messenger=input_messenger
    )

    should_messenger_finish = True
    try:
        messenger.log_status(TaskStatus.RUNNING, "Script started.")

        credential_store = CredentialStore(
            messenger=messenger,
            request_input=(
                InputPolicy.ALWAYS if args.force_input else InputPolicy.AS_REQUIRED
            ),
        )

        all_logins_succeeded = True
        if "boxcast" in args.credentials:
            all_logins_succeeded = all_logins_succeeded and _try_login_to_boxcast(
                credential_store=credential_store,
                messenger=messenger,
                log_dir=log_dir,
                show_browser=args.show_browser,
            )
        if "vimeo" in args.credentials:
            all_logins_succeeded = all_logins_succeeded and _try_login_to_vimeo(
                credential_store=credential_store, messenger=messenger
            )

        if all_logins_succeeded:
            messenger.log_status(TaskStatus.DONE, "Everything looks good!")
        else:
            messenger.log_status(
                TaskStatus.DONE,
                'Some logins failed. See the "Problems" section for more details.',
            )
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
            TaskStatus.DONE,
            'An unexpected error forced the program to stop. See the "Problems" section for more details.',
        )
    finally:
        messenger.close(wait=should_messenger_finish)


def _try_login_to_vimeo(
    credential_store: CredentialStore, messenger: Messenger
) -> bool:
    try:
        messenger.set_current_task_name("log_into_vimeo")
        messenger.log_status(TaskStatus.RUNNING, "Task started.")
        ReccVimeoClient(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
            # Since lazy_login = false, the login should be tested eagerly
            lazy_login=False,
        )
        messenger.log_status(TaskStatus.DONE, "Successfully connected to Vimeo.")
        return True
    except Exception as e:
        messenger.log_problem(
            ProblemLevel.ERROR,
            f"An error occurred while trying to log into Vimeo: {e}",
            stacktrace=traceback.format_exc(),
        )
        messenger.log_status(TaskStatus.DONE, "Login failed.")
        return False
    finally:
        messenger.set_current_task_name(Messenger.ROOT_PSEUDOTASK_NAME)


def _try_login_to_boxcast(
    credential_store: CredentialStore,
    messenger: Messenger,
    log_dir: Path,
    show_browser: bool,
) -> bool:
    try:
        messenger.set_current_task_name("log_into_boxcast")
        messenger.log_status(TaskStatus.RUNNING, "Task started.")
        BoxCastClientFactory(
            messenger=messenger,
            credential_store=credential_store,
            cancellation_token=None,
            headless=not show_browser,
            # Since lazy_login = false, the login should be tested eagerly
            lazy_login=False,
            log_directory=log_dir,
            log_file_name="check_credentials_web_driver",
        )
        messenger.log_status(
            TaskStatus.DONE,
            f"Successfully logged into BoxCast as {credential_store.get(Credential.BOXCAST_USERNAME, request_input=InputPolicy.NEVER)}",
        )
        return True
    except Exception as e:
        messenger.log_problem(
            ProblemLevel.ERROR,
            f"An error occurred while trying to log into BoxCast: {e}",
            stacktrace=traceback.format_exc(),
        )
        messenger.log_status(TaskStatus.DONE, "Login failed.")
        return False
    finally:
        messenger.set_current_task_name(Messenger.ROOT_PSEUDOTASK_NAME)


def _parse_args() -> Namespace:
    parser = ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "-f",
        "--force-input",
        action="store_true",
        help="If this flag is provided, then the user will be asked to enter all credentials regardless of whether they have previously been stored.",
    )
    parser.add_argument(
        "-c",
        "--credentials",
        action="append",
        choices=["boxcast", "vimeo"],
        help="Which credentials to check.",
    )

    advanced_args = parser.add_argument_group("Advanced arguments")
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
    advanced_args.add_argument(
        "--text-ui",
        action="store_true",
        help="If this flag is provided, then user interactions will be performed via a simpler terminal-based UI.",
    )

    args = parser.parse_args()
    if not args.credentials:
        args.credentials = ["boxcast", "vimeo"]

    return args


if __name__ == "__main__":
    main()
