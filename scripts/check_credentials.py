import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable, List, Literal, Set, Tuple

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
from config import Config, ReccArgs
from external_services import (
    BoxCastClientFactory,
    Credential,
    CredentialStore,
    InputPolicy,
    PlanningCenterClient,
    ReccVimeoClient,
)

CredentialName = Literal["boxcast", "vimeo", "planning_center"]
ALL_CREDENTIALS: Set[CredentialName] = {"boxcast", "vimeo", "planning_center"}


class CheckCredentialsArgs(ReccArgs):
    NAME = "check_credentials"
    DESCRIPTION = "This script will test the credentials for various services we connect to and ask you to enter any missing or incorrect ones if necessary."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.credentials: Set[CredentialName] = set(args.credentials or ALL_CREDENTIALS)
        self.force_input: bool = args.force_input
        self.show_browser: bool = args.show_browser

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-c",
            "--credentials",
            action="append",
            choices=ALL_CREDENTIALS,
            help="Which credentials to check.",
        )
        parser.add_argument(
            "-f",
            "--force-input",
            action="store_true",
            help="If this flag is provided, then the user will be asked to enter all credentials regardless of whether they have previously been stored.",
        )
        parser.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )
        return super().set_up_parser(parser)


class CheckCredentialsScript(Script[CheckCredentialsArgs, Config]):
    def parse_args(self) -> CheckCredentialsArgs:
        return CheckCredentialsArgs.parse(sys.argv)

    def create_config(self, args: CheckCredentialsArgs) -> Config:
        return Config(args)

    def create_messenger(self, args: CheckCredentialsArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(log_file=config.check_credentials_log)
        input_messenger = (
            ConsoleMessenger(
                description=CheckCredentialsArgs.DESCRIPTION,
                show_task_status=args.verbose,
            )
            if args.ui == "console"
            else TkMessenger(
                title="Check Credentials", description=CheckCredentialsArgs.DESCRIPTION
            )
        )
        messenger = Messenger(file_messenger, input_messenger)
        return messenger

    def create_services(
        self, args: CheckCredentialsArgs, config: Config, messenger: Messenger
    ) -> Tuple[TaskModel | Path, FunctionFinder]:
        subtasks: List[TaskModel] = []
        if "boxcast" in args.credentials:
            subtasks.append(
                TaskModel(
                    name="log_into_boxcast",
                    description="Failed to log into BoxCast.",
                    only_auto=True,
                )
            )
        if "planning_center" in args.credentials:
            subtasks.append(
                TaskModel(
                    name="log_into_planning_center",
                    description="Failed to connect to the Planning Center API.",
                    only_auto=True,
                )
            )
        if "vimeo" in args.credentials:
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
                InputPolicy.ALWAYS if args.force_input else InputPolicy.AS_REQUIRED
            ),
        )
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[messenger, credential_store, config],
            messenger=messenger,
        )
        return task_model, function_finder


def log_into_vimeo(
    config: Config, credential_store: CredentialStore, messenger: Messenger
) -> None:
    ReccVimeoClient(
        messenger=messenger,
        credential_store=credential_store,
        config=config,
        cancellation_token=None,
        # Since lazy_login = false, the login should be tested eagerly
        lazy_login=False,
    )
    messenger.log_status(TaskStatus.DONE, "Successfully connected to Vimeo.")


def log_into_boxcast(
    config: Config,
    credential_store: CredentialStore,
    messenger: Messenger,
    show_browser: bool,
) -> None:
    cancellation_token = messenger.allow_cancel()
    BoxCastClientFactory(
        messenger=messenger,
        credential_store=credential_store,
        cancellation_token=cancellation_token,
        headless=not show_browser,
        # Since lazy_login = false, the login should be tested eagerly
        lazy_login=False,
        log_directory=config.log_dir,
        log_file_name=config.check_credentials_webdriver_log_name,
    )
    messenger.log_status(
        TaskStatus.DONE,
        f"Successfully logged into BoxCast as {credential_store.get(Credential.BOXCAST_USERNAME, request_input=InputPolicy.NEVER)}",
    )


def log_into_planning_center(
    config: Config, credential_store: CredentialStore, messenger: Messenger
) -> None:
    PlanningCenterClient(
        messenger=messenger,
        credential_store=credential_store,
        config=config,
        lazy_login=False,
    )
    messenger.log_status(
        TaskStatus.DONE, "Successfully connected to the Planning Center API."
    )


if __name__ == "__main__":
    CheckCredentialsScript().run()
