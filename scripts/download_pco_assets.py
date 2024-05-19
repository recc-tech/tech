import sys
from argparse import ArgumentParser, Namespace
from typing import Callable

import autochecklist
from args import ReccArgs
from autochecklist import Messenger, TaskModel, TaskStatus
from config import Config
from external_services import PlanningCenterClient
from lib import AssetManager, ReccDependencyProvider


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
    args = DownloadAssetsArgs.parse(sys.argv)
    config = Config(args)
    tasks = TaskModel(
        name="download_PCO_assets",
        description="Failed to download assets.",
        only_auto=True,
    )
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.download_assets_log,
        script_name="Download PCO Assets",
        description=DownloadAssetsArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dependency_provider,
        tasks=tasks,
        module=sys.modules[__name__],
    )
