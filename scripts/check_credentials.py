import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Set, Tuple

import lib
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Script,
    TaskModel,
    TaskStatus,
    TkMessenger,
)
from config import ReccConfig
from external_services import (
    BoxCastClientFactory,
    Credential,
    CredentialStore,
    InputPolicy,
    PlanningCenterClient,
    ReccVimeoClient,
)

DESCRIPTION = "This script will test the credentials for various services we connect to and ask you to enter any missing or incorrect ones if necessary."


class CheckCredentialsConfig(ReccConfig):
    def __init__(
        self,
        credentials: Set[str],
        force_input: bool,
        show_browser: bool,
        home_dir: Path,
        now: datetime,
        ui: Literal["console", "tk"],
        verbose: bool,
        no_run: bool,
    ) -> None:
        super().__init__(
            home_dir=home_dir,
            now=now,
            ui=ui,
            verbose=verbose,
            no_run=no_run,
            auto_tasks=None,
        )
        self.show_browser = show_browser
        self.credentials = credentials
        self.force_input = force_input

    @property
    def log_file(self) -> Path:
        timestamp = f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')}"
        return self.log_dir.joinpath(f"{timestamp} check_credentials.log")


class CheckCredentialsScript(Script[CheckCredentialsConfig]):
    def create_config(self) -> CheckCredentialsConfig:
        all_credentials = {"boxcast", "vimeo", "planning_center"}
        parser = ArgumentParser(description=DESCRIPTION)
        parser.add_argument(
            "-c",
            "--credentials",
            action="append",
            choices=all_credentials,
            help="Which credentials to check.",
        )
        parser.add_argument(
            "-f",
            "--force-input",
            action="store_true",
            help="If this flag is provided, then the user will be asked to enter all credentials regardless of whether they have previously been stored.",
        )

        advanced_args = parser.add_argument_group("Advanced arguments")
        advanced_args.add_argument(
            "--home-dir",
            type=lib.parse_directory,
            default="D:\\Users\\Tech\\Documents",
            help="The home directory.",
        )
        advanced_args.add_argument(
            "--ui",
            choices=["console", "tk"],
            default="tk",
            help="User interface to use.",
        )

        debug_args = parser.add_argument_group("Debug arguments")
        debug_args.add_argument(
            "--verbose",
            action="store_true",
            help="This flag is only applicable when the console UI is used. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
        )
        debug_args.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )

        args = parser.parse_args()
        return CheckCredentialsConfig(
            credentials=set(args.credentials or all_credentials),
            force_input=args.force_input,
            show_browser=args.show_browser,
            home_dir=args.home_dir,
            now=datetime.now(),
            ui=args.ui,
            verbose=args.verbose,
            no_run=False,
        )

    def create_messenger(self, config: CheckCredentialsConfig) -> Messenger:
        file_messenger = FileMessenger(log_file=config.log_file)
        input_messenger = (
            ConsoleMessenger(description=DESCRIPTION, show_task_status=config.verbose)
            if config.ui == "console"
            else TkMessenger(title="Check Credentials", description=DESCRIPTION)
        )
        messenger = Messenger(file_messenger, input_messenger)
        return messenger

    def create_services(
        self, config: CheckCredentialsConfig, messenger: Messenger
    ) -> Tuple[TaskModel | Path, FunctionFinder]:
        subtasks: List[TaskModel] = []
        if "boxcast" in config.credentials:
            subtasks.append(
                TaskModel(
                    name="log_into_boxcast",
                    description="Failed to log into BoxCast.",
                    only_auto=True,
                )
            )
        if "planning_center" in config.credentials:
            subtasks.append(
                TaskModel(
                    name="log_into_planning_center",
                    description="Failed to connect to the Planning Center API.",
                    only_auto=True,
                )
            )
        if "vimeo" in config.credentials:
            subtasks.append(
                TaskModel(
                    name="log_into_vimeo",
                    description="Failed to connect to the Vimeo API.",
                    only_auto=True,
                )
            )

        task_model = TaskModel(name="check_credentials", subtasks=subtasks)
        credential_store = CredentialStore(
            messenger=messenger,
            request_input=(
                InputPolicy.ALWAYS if config.force_input else InputPolicy.AS_REQUIRED
            ),
        )
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[messenger, credential_store, config],
            messenger=messenger,
        )
        return task_model, function_finder


def log_into_vimeo(credential_store: CredentialStore, messenger: Messenger) -> None:
    ReccVimeoClient(
        messenger=messenger,
        credential_store=credential_store,
        cancellation_token=None,
        # Since lazy_login = false, the login should be tested eagerly
        lazy_login=False,
    )
    messenger.log_status(TaskStatus.DONE, "Successfully connected to Vimeo.")


def log_into_boxcast(
    credential_store: CredentialStore,
    messenger: Messenger,
    config: CheckCredentialsConfig,
) -> None:
    cancellation_token = messenger.allow_cancel()
    BoxCastClientFactory(
        messenger=messenger,
        credential_store=credential_store,
        cancellation_token=cancellation_token,
        headless=not config.show_browser,
        # Since lazy_login = false, the login should be tested eagerly
        lazy_login=False,
        log_directory=config.log_dir,
        log_file_name="check_credentials_webdriver",
    )
    messenger.log_status(
        TaskStatus.DONE,
        f"Successfully logged into BoxCast as {credential_store.get(Credential.BOXCAST_USERNAME, request_input=InputPolicy.NEVER)}",
    )


def log_into_planning_center(
    credential_store: CredentialStore, messenger: Messenger
) -> None:
    PlanningCenterClient(
        messenger=messenger,
        credential_store=credential_store,
        lazy_login=False,
    )
    messenger.log_status(
        TaskStatus.DONE, "Successfully connected to the Planning Center API."
    )


if __name__ == "__main__":
    CheckCredentialsScript().run()
