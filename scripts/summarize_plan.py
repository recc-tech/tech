import subprocess
import sys
import traceback
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable

import autochecklist
import lib
from args import ReccArgs
from autochecklist import Messenger, ProblemLevel, TaskModel, TaskStatus
from config import Config
from external_services import PlanningCenterClient
from lib import ReccDependencyProvider

_DEMO_FILE = Path(__file__).parent.joinpath(
    "test", "integration", "summarize_plan_data", "20240414_summary.json"
)


class SummarizePlanArgs(ReccArgs):
    DESCRIPTION = "This script will generate a summary of the plan for today's service."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        self.no_open: bool = args.no_open
        self.demo: bool = args.demo
        super().__init__(args, error)

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--no-open",
            action="store_true",
            help="Do not open the summary in the browser.",
        )
        parser.add_argument(
            "--demo",
            action="store_true",
            help="Show a summary of a previous service to show the appearance, rather than pulling up-to-date data from Planning Center.",
        )
        return super().set_up_parser(parser)


def summarize_plan(
    pco_client: PlanningCenterClient,
    args: SummarizePlanArgs,
    config: Config,
    messenger: Messenger,
) -> None:
    if args.demo:
        summary = lib.load_plan_summary(_DEMO_FILE)
    else:
        summary = lib.get_plan_summary(
            client=pco_client,
            messenger=messenger,
            config=config,
            dt=config.start_time.date(),
        )
    html = lib.plan_summary_to_html(summary)
    config.plan_summary_file.parent.mkdir(parents=True, exist_ok=True)
    config.plan_summary_file.write_text(str(html), encoding="utf-8")
    messenger.log_status(
        TaskStatus.DONE, f"Saved summary at {config.plan_summary_file.as_posix()}."
    )
    if not args.no_open:
        try:
            # Use Popen so this doesn't block
            subprocess.Popen(["firefox", config.plan_summary_file.as_posix()])
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Failed to open summary in Firefox: {e}.",
                traceback.format_exc(),
            )


def main(args: SummarizePlanArgs, config: Config, dep: ReccDependencyProvider) -> None:
    tasks = TaskModel(
        "summarize_plan",
        description="Failed to generate summary.",
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
    args = SummarizePlanArgs.parse(sys.argv)
    config = Config(args)
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.summarize_plan_log,
        script_name="Summarize Plan",
        description=SummarizePlanArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    main(args, config, dependency_provider)
