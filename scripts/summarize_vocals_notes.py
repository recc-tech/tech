import sys
import traceback
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable

import autochecklist
import external_services
import lib
from args import ReccArgs
from autochecklist import Messenger, ProblemLevel, TaskModel, TaskStatus
from config import Config
from external_services import PlanningCenterClient
from lib import ReccDependencyProvider, SimplifiedMessengerSettings

_DEMO_FILE = Path(__file__).parent.joinpath(
    "test", "integration", "summarize_plan_data", "20240505_vocals_notes.json"
)


class SummarizeVocalsNotesArgs(ReccArgs):
    NAME = "summarize_vocals_notes"
    DESCRIPTION = (
        "This script will generate a summary of the vocals notes in today's service."
    )

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


def summarize_vocals_notes(
    pco_client: PlanningCenterClient,
    args: SummarizeVocalsNotesArgs,
    config: Config,
    messenger: Messenger,
) -> None:
    if args.demo:
        summary = lib.load_vocals_notes(_DEMO_FILE)
    else:
        summary = lib.get_vocals_notes(
            client=pco_client,
            config=config,
            dt=config.start_time.date(),
        )
    html = lib.vocals_notes_to_html(summary)
    config.vocals_notes_file.parent.mkdir(parents=True, exist_ok=True)
    config.vocals_notes_file.write_text(str(html), encoding="utf-8")
    url = config.vocals_notes_file.resolve().as_uri()
    try:
        fname = config.vocals_notes_file.relative_to(config.home_dir).as_posix()
    except ValueError:
        fname = config.vocals_notes_file.as_posix()
    messenger.log_status(TaskStatus.DONE, f"Saved summary at [[url|{url}|{fname}]].")
    if not args.no_open:
        try:
            external_services.launch_firefox(config.vocals_notes_file.as_posix())
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Failed to open summary in Firefox: {e}.",
                traceback.format_exc(),
            )


def main(
    args: SummarizeVocalsNotesArgs, config: Config, dep: ReccDependencyProvider
) -> None:
    tasks = TaskModel(
        "summarize_vocals_notes",
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
    _args = SummarizeVocalsNotesArgs.parse(sys.argv)
    _cfg = Config(_args)
    msg = SimplifiedMessengerSettings(
        log_file=_cfg.summarize_plan_log,
        script_name="Summarize Plan",
        description=SummarizeVocalsNotesArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    dependency_provider = ReccDependencyProvider(
        args=_args, config=_cfg, messenger=msg, lazy_login=_args.demo
    )
    main(_args, _cfg, dependency_provider)
