import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable, Tuple, Union

import lib
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
from external_services import CredentialStore, PlanningCenterClient


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
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[args, config, planning_center_client, messenger],
            messenger=messenger,
        )
        task_model = TaskModel(
            name="download_pco_assets",
            description="Failed to download assets.",
            only_auto=True,
        )
        return task_model, function_finder


def download_pco_assets(
    args: DownloadAssetsArgs,
    config: Config,
    client: PlanningCenterClient,
    messenger: Messenger,
):
    lib.download_pco_assets(
        client=client,
        messenger=messenger,
        today=args.start_time.date(),
        assets_by_service_dir=config.assets_by_service_dir,
        temp_assets_dir=config.temp_assets_dir,
        assets_by_type_videos_dir=config.videos_dir,
        assets_by_type_images_dir=config.images_dir,
        download_kids_video=config.station == "mcr",
        download_notes_docx=config.station == "foh",
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    DownloadAssetsScript().run()
