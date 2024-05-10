import sys
from datetime import datetime, time, timedelta
from typing import Tuple

from args import ReccArgs
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Script,
    TaskModel,
    TkMessenger,
)
from config import Config
from external_services import BoxCastApiClient, CredentialStore

_BROADCAST_ID = "orn5qh81x7dojxwlbbng"
_REBROADCAST_TITLE = f"Test Rebroadcast {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
_REBROADCAST_START = datetime.combine(
    date=datetime.now().date() + timedelta(days=1),
    time=time(hour=13, minute=3, second=14),
)


class ManualTestArgs(ReccArgs):
    NAME = "test_manually"
    DESCRIPTION = "This script will guide you through testing parts of the project for which fully automated testing is impractical."


class ManualTestScript(Script[ManualTestArgs, Config]):
    def parse_args(self) -> ManualTestArgs:
        return ManualTestArgs.parse(sys.argv)

    def create_config(self, args: ReccArgs) -> Config:
        return Config(args)

    def create_messenger(self, args: ReccArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(config.schedule_rebroadcast_log)
        input_messenger = (
            TkMessenger(
                "Autochecklist",
                ManualTestArgs.DESCRIPTION,
                theme=config.ui_theme,
                show_statuses_by_default=True,
            )
            if args.ui == "tk"
            else ConsoleMessenger(
                ManualTestArgs.DESCRIPTION, show_task_status=args.verbose
            )
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, args: ManualTestArgs, config: Config, messenger: Messenger
    ) -> Tuple[TaskModel, FunctionFinder]:
        credential_store = CredentialStore(messenger=messenger)
        client = BoxCastApiClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            lazy_login=False,
        )
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[client],
            messenger=messenger,
        )
        task_model = TaskModel(
            name="test_manually",
            subtasks=[
                TaskModel(
                    name="ready",
                    description="Press 'Done' once you are ready to start testing.",
                ),
                TaskModel(
                    name="test_schedule_rebroadcast",
                    subtasks=[
                        TaskModel(
                            name="ready_schedule_rebroadcast",
                            description=(
                                f"The next task should create a broadcast called '{_REBROADCAST_TITLE}' starting at {_REBROADCAST_START.strftime('%Y-%m-%d %H:%M:%S')}."
                                + f" [IMPORTANT] You should log into BoxCast using the owner account before starting."
                            ),
                        ),
                        TaskModel(
                            name="schedule_rebroadcast",
                            description="Failed to schedule rebroadcast.",
                            only_auto=True,
                            prerequisites={"ready_schedule_rebroadcast"},
                        ),
                        TaskModel(
                            name="delete_rebroadcast",
                            description="Go to BoxCast, check that the rebroadcast was created properly, and then delete it.",
                            prerequisites={"schedule_rebroadcast"},
                        ),
                    ],
                    prerequisites={"ready"},
                ),
            ],
        )
        return task_model, function_finder


def schedule_rebroadcast(client: BoxCastApiClient) -> None:
    client.schedule_rebroadcast(
        broadcast_id=_BROADCAST_ID, name=_REBROADCAST_TITLE, start=_REBROADCAST_START
    )


if __name__ == "__main__":
    ManualTestScript().run()
