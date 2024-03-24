import subprocess
import sys
import traceback
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
    ProblemLevel,
    Script,
    TaskModel,
    TaskStatus,
    TkMessenger,
)
from config import Config
from external_services import CredentialStore, PlanningCenterClient


class SummarizePlanArgs(ReccArgs):
    DESCRIPTION = "This script will generate a summary of the plan for today's service."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        self.no_open: bool = args.no_open
        super().__init__(args, error)

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--no-open",
            action="store_true",
            help="Do not open the summary in the browser.",
        )
        return super().set_up_parser(parser)


class SummarizePlanScript(Script[SummarizePlanArgs, Config]):
    def parse_args(self) -> SummarizePlanArgs:
        return SummarizePlanArgs.parse(sys.argv)

    def create_config(self, args: ReccArgs) -> Config:
        return Config(args)

    def create_messenger(self, args: ReccArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(config.summarize_plan_log)
        input_messenger = (
            ConsoleMessenger(
                f"{args.DESCRIPTION}\n\nIf you need to stop the script, press CTRL+C or close the terminal window.",
                show_task_status=args.verbose,
            )
            if args.ui == "console"
            else TkMessenger(
                title="Summarize Plan",
                description=args.DESCRIPTION,
                theme=config.ui_theme,
                show_statuses_by_default=True,
            )
        )
        messenger = Messenger(
            file_messenger=file_messenger, input_messenger=input_messenger
        )
        return messenger

    def create_services(
        self, args: SummarizePlanArgs, config: Config, messenger: Messenger
    ) -> Tuple[Union[TaskModel, Path], FunctionFinder]:
        credential_store = CredentialStore(messenger=messenger)
        pco_client = PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
        )
        finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[args, config, messenger, pco_client],
            messenger=messenger,
        )
        task_model = TaskModel(
            "summarize_plan",
            description="Failed to generate summary.",
            only_auto=True,
        )
        return (task_model, finder)


def summarize_plan(
    pco_client: PlanningCenterClient,
    args: SummarizePlanArgs,
    config: Config,
    messenger: Messenger,
) -> None:
    summary = lib.get_plan_summary(
        client=pco_client, messenger=messenger, dt=config.start_time.date()
    )
    html = lib.plan_summary_to_html(summary)
    config.plan_summary_file.parent.mkdir(parents=True, exist_ok=True)
    config.plan_summary_file.write_text(str(html))
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


if __name__ == "__main__":
    SummarizePlanScript().run()
