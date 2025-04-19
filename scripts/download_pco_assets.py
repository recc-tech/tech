import sys
from argparse import ArgumentParser, Namespace
from typing import Callable, Literal, Optional

import autochecklist
from args import ReccArgs
from autochecklist import Messenger, TaskModel, TaskStatus
from config import Config
from external_services import PlanningCenterClient
from lib import AssetManager, ReccDependencyProvider, SimplifiedMessengerSettings


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


class DownloadAssetsConfig(Config):
    def __init__(
        self,
        args: ReccArgs,
        profile: Optional[str] = None,
        strict: bool = False,
        allow_multiple_only_for_testing: bool = False,
    ) -> None:
        self._args = args
        super().__init__(
            args,
            profile=profile,
            strict=strict,
            allow_multiple_only_for_testing=allow_multiple_only_for_testing,
        )

    # Don't error out even if assets are missing.
    # That way, this script can be used as a fallback in case the MCR setup
    # script gets stuck due to missing assets but the user wants to keep
    # working.

    @property
    def if_announcements_vid_missing(self) -> Literal["ok", "warn", "error"]:
        return "warn"

    @property
    def if_kids_vid_missing(self) -> Literal["ok", "warn", "error"]:
        return "warn"

    @property
    def if_sermon_notes_missing(self) -> Literal["ok", "warn", "error"]:
        return "warn"


def download_PCO_assets(
    args: DownloadAssetsArgs,
    config: DownloadAssetsConfig,
    client: PlanningCenterClient,
    messenger: Messenger,
    manager: AssetManager,
):
    pco_plan = client.find_plan_by_date(config.start_time.date())
    attachments = client.find_attachments(pco_plan.id)
    download_plan = manager.plan_downloads(attachments=attachments, messenger=messenger)
    if args.dry_run:
        messenger.log_debug("Skipping downloading assets: dry run.")
        msg = "\n".join(
            [f"* {a.filename}: {d}" for (a, d) in download_plan.downloads.items()]
        )
        messenger.log_status(TaskStatus.DONE, msg)
    results = manager.execute_plan(
        plan=download_plan,
        pco_client=client,
        messenger=messenger,
    )
    msg = "\n".join([f"* {a.filename}: {res}" for (a, res) in results.items()])
    messenger.log_status(TaskStatus.DONE, msg)


def main(
    args: DownloadAssetsArgs, config: DownloadAssetsConfig, dep: ReccDependencyProvider
) -> None:
    tasks = TaskModel(
        name="download_PCO_assets",
        description="Failed to download assets.",
        only_auto=True,
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=tasks,
        module=sys.modules[__name__],
    )


if __name__ == "__main__":
    args = DownloadAssetsArgs.parse(sys.argv)
    config = DownloadAssetsConfig(args)
    msg = SimplifiedMessengerSettings(
        log_file=config.download_assets_log,
        script_name="Download PCO Assets",
        description=DownloadAssetsArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    dependency_provider = ReccDependencyProvider(
        args=args, config=config, messenger=msg
    )
    main(args, config, dependency_provider)
