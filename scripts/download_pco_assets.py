import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable, Tuple, Union

from args import ReccArgs
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
from config import Config
from external_services import CredentialStore, PlanningCenterClient
from lib import AssetManager


class DownloadAssetsArgs(ReccArgs):
    NAME = "download_pco_assets"
    DESCRIPTION = "This script will download the assets from today's plan in Planning Center Online."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.dry_run: bool = args.dry_run

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Detect available assets without actually downloading any.",
        )
        return super().set_up_parser(parser)


class DownloadAssetsScript(Script[DownloadAssetsArgs, Config]):
    def parse_args(self) -> DownloadAssetsArgs:
        return DownloadAssetsArgs.parse(sys.argv)

    def create_config(self, args: DownloadAssetsArgs) -> Config:
        return Config(args)

    def create_messenger(self, args: DownloadAssetsArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(config.download_assets_log)
        input_messenger = (
            TkMessenger(
                "Autochecklist",
                DownloadAssetsArgs.DESCRIPTION,
                theme=config.ui_theme,
                show_statuses_by_default=True,
            )
            if args.ui == "tk"
            else ConsoleMessenger(
                DownloadAssetsArgs.DESCRIPTION, show_task_status=args.verbose
            )
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, args: DownloadAssetsArgs, config: Config, messenger: Messenger
    ) -> Tuple[Union[Path, TaskModel], FunctionFinder]:
        credential_store = CredentialStore(messenger)
        planning_center_client = PlanningCenterClient(
            messenger, credential_store, config
        )
        manager = AssetManager(config)
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[args, config, planning_center_client, messenger, manager],
            messenger=messenger,
        )
        task_model = TaskModel(
            name="download_PCO_assets",
            description="Failed to download assets.",
            only_auto=True,
        )
        return task_model, function_finder


def download_PCO_assets(
    args: DownloadAssetsArgs,
    config: Config,
    client: PlanningCenterClient,
    messenger: Messenger,
    manager: AssetManager,
):
    results = manager.download_pco_assets(
        client=client,
        messenger=messenger,
        download_kids_video=config.station == "mcr",
        download_notes_docx=config.station == "mcr",
        require_announcements=config.station == "foh",
        dry_run=args.dry_run,
    )
    msg = "\n".join([f"* {a.filename}: {res}" for (a, res) in results.items()])
    messenger.log_status(TaskStatus.DONE, msg)


if __name__ == "__main__":
    DownloadAssetsScript().run()
