import sys
import typing
from datetime import datetime
from typing import Tuple

import args.parsing_helpers as parse
from args import ReccArgs
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Parameter,
    Script,
    TaskModel,
    TkMessenger,
)
from config import Config
from external_services import BoxCastApiClient, CredentialStore


class RebroadcastArgs(ReccArgs):
    NAME = "schedule_rebroadcast"
    DESCRIPTION = "This script will schedule a rebroadcast on BoxCast. It is mainly intended for testing."


class RebroadcastScript(Script[RebroadcastArgs, Config]):
    def parse_args(self) -> RebroadcastArgs:
        return RebroadcastArgs.parse(sys.argv)

    def create_config(self, args: ReccArgs) -> Config:
        return Config(args)

    def create_messenger(self, args: ReccArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(config.schedule_rebroadcast_log)
        input_messenger = (
            TkMessenger(
                "Autochecklist",
                RebroadcastArgs.DESCRIPTION,
                theme=config.ui_theme,
                show_statuses_by_default=True,
            )
            if args.ui == "tk"
            else ConsoleMessenger(
                RebroadcastArgs.DESCRIPTION, show_task_status=args.verbose
            )
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, args: RebroadcastArgs, config: Config, messenger: Messenger
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
            arguments=[client, messenger],
            messenger=messenger,
        )
        task_model = TaskModel(
            name="schedule_rebroadcast",
            description="Failed to schedule rebroadcast.",
            only_auto=True,
        )
        return task_model, function_finder


def schedule_rebroadcast(client: BoxCastApiClient, messenger: Messenger) -> None:
    params = {
        "broadcast_id": Parameter(
            "Source Broadcast ID",
            parser=parse.parse_non_empty_string,
            description="ID of the broadcast from which to create the rebroadcast.",
        ),
        "name": Parameter(
            "Rebroadcast Name",
            parser=parse.parse_non_empty_string,
            description="Title of the rebroadcast.",
        ),
        "start": Parameter(
            "Start Date and Time",
            parser=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S"),
            description="Start date and time (YYYY-MM-DD HH:MM:SS).",
        ),
    }
    inputs = messenger.input_multiple(
        params=params,
        prompt="Enter info for the rebroadcast.",
    )
    broadcast_id = typing.cast(str, inputs["broadcast_id"])
    name = typing.cast(str, inputs["name"])
    start = typing.cast(datetime, inputs["start"])
    client.schedule_rebroadcast(broadcast_id=broadcast_id, name=name, start=start)


if __name__ == "__main__":
    RebroadcastScript().run()
