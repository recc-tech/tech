import sys
from argparse import ArgumentParser, Namespace
from typing import Callable, List, Literal

import autochecklist
from args import ReccArgs
from autochecklist import Messenger, ProblemLevel, TaskModel, TaskStatus
from config import Config
from external_services import (
    Credential,
    CredentialStore,
    InputPolicy,
    PlanningCenterClient,
    bird_dog,
)
from external_services.boxcast import BoxCastApiClient
from external_services.vimeo import ReccVimeoClient
from lib import ReccDependencyProvider, SimplifiedMessengerSettings
from requests import Session


class CheckCredentialsArgs(ReccArgs):
    NAME = "check_credentials"
    DESCRIPTION = "This script will test the credentials for various services we connect to and ask you to enter any missing or incorrect ones if necessary."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.force_input: bool = args.force_input

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-f",
            "--force-input",
            action="store_true",
            help="If this flag is provided, then the user will be asked to enter all credentials regardless of whether they have previously been stored.",
        )
        return super().set_up_parser(parser)


def log_into_Vimeo(
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


def log_into_BoxCast(
    config: Config, credential_store: CredentialStore, messenger: Messenger
) -> None:
    BoxCastApiClient(
        messenger=messenger,
        credential_store=credential_store,
        config=config,
        # Since lazy_login = false, the login should be tested eagerly
        lazy_login=False,
    )
    messenger.log_status(TaskStatus.DONE, "Successfully connected to BoxCast.")


def log_into_Planning_Center(
    config: Config, credential_store: CredentialStore, messenger: Messenger
) -> None:
    PlanningCenterClient(
        messenger=messenger,
        credential_store=credential_store,
        config=config,
        # Since lazy_login = false, the login should be tested eagerly
        lazy_login=False,
    )
    messenger.log_status(TaskStatus.DONE, "Successfully connected to Planning Center.")


def log_into_BirdDog(
    config: Config, credential_store: CredentialStore, messenger: Messenger
) -> None:
    all_cameras: List[Literal[1, 2, 3]] = [1, 2, 3]
    for camera in all_cameras:
        messenger.log_status(TaskStatus.RUNNING, f"Testing cam {camera}...")
        first_try = True
        while True:
            password = credential_store.get(
                Credential.BIRD_DOG_PASSWORD,
                InputPolicy.AS_REQUIRED if first_try else InputPolicy.ALWAYS,
            )
            first_try = False
            with Session() as s:
                bird_dog.log_in(camera, s, config, password)
                if s.cookies.get("BirdDogSession"):
                    break
                messenger.log_problem(
                    ProblemLevel.ERROR,
                    "Failed to log in (cookie 'BirdDogSession' is not set)",
                )
    messenger.log_status(
        TaskStatus.DONE,
        f"Successfully connected to cameras {', '.join([str(c) for c in all_cameras])}.",
    )


def main(
    args: CheckCredentialsArgs, config: Config, dep: ReccDependencyProvider
) -> None:
    tasks = TaskModel(
        name="check_credentials",
        subtasks=[
            TaskModel(
                name="log_into_BoxCast",
                description="Failed to log into BoxCast.",
                only_auto=True,
            ),
            TaskModel(
                name="log_into_Planning_Center",
                description="Failed to connect to the Planning Center API.",
                only_auto=True,
            ),
            TaskModel(
                name="log_into_Vimeo",
                description="Failed to connect to the Vimeo API.",
                only_auto=True,
            ),
            TaskModel(
                name="log_into_BirdDog",
                description="Failed to connect to the BirdDog cameras.",
                only_auto=True,
            ),
        ],
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=tasks,
        module=sys.modules[__name__],
    )


if __name__ == "__main__":
    args = CheckCredentialsArgs.parse(sys.argv)
    config = Config(args)
    msg = SimplifiedMessengerSettings(
        log_file=config.check_credentials_log,
        script_name="Check Credentials",
        description=CheckCredentialsArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        messenger=msg,
        credentials_input_policy=(
            InputPolicy.ALWAYS if args.force_input else InputPolicy.AS_REQUIRED
        ),
    )
    main(args, config, dependency_provider)
