import os
import signal
import sys
import traceback
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable, Optional

import autochecklist
import bottle  # pyright: ignore[reportMissingTypeStubs]
import external_services
import lib
from args import ReccArgs
from autochecklist import Messenger, ProblemLevel, TaskModel, TaskStatus
from config import Config
from external_services import PlanningCenterClient
from lib import PlanItemsSummary, ReccDependencyProvider

_DEMO_FILE = Path(__file__).parent.joinpath(
    "test", "integration", "summarize_plan_data", "20240414_summary.json"
)


class SummarizePlanArgs(ReccArgs):
    NAME = "summarize_plan"
    DESCRIPTION = "This script will generate a summary of the plan for today's service."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        self.no_open: bool = args.no_open
        self.demo: bool = args.demo
        self.port: int = args.port
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
        parser.add_argument(
            "--port",
            type=int,
            default=8080,
            help="Which port to use for the web server that checks for updates.",
        )
        return super().set_up_parser(parser)


def main(args: SummarizePlanArgs, config: Config, dep: ReccDependencyProvider) -> None:
    tasks = TaskModel(
        "summarize_plan",
        subtasks=[
            TaskModel(
                "generate_initial_summary",
                description="An error occurred while generating the initial summary.",
                only_auto=True,
            ),
            TaskModel(
                "listen_for_updates",
                description="An error occurred while listening for updates.",
                only_auto=True,
                prerequisites={"generate_initial_summary"},
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
    _stop_server()


def generate_initial_summary(
    pco_client: PlanningCenterClient,
    args: SummarizePlanArgs,
    config: Config,
    messenger: Messenger,
) -> None:
    _generate_and_save_summary(
        pco_client=pco_client,
        messenger=messenger,
        args=args,
        config=config,
        prev_summary=None,
    )

    html_path = config.plan_summary_html_file
    url = html_path.resolve().as_uri()
    try:
        fname = html_path.relative_to(config.home_dir).as_posix()
    except ValueError:
        fname = html_path.as_posix()
    messenger.log_status(TaskStatus.RUNNING, f"Saved summary at [[url|{url}|{fname}]].")

    if not args.no_open:
        try:
            external_services.launch_firefox(html_path.as_posix())
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Failed to open summary in Firefox: {e}.",
                traceback.format_exc(),
            )


# Use global variables to keep track of services (e.g., the
# `PlanningCenterClient` and `Messenger`).
# Maybe it's a bit gross, but other solutions (e.g., writing to a file or a
# database) would surely be more complex and might not work for services.
global_pco_client: PlanningCenterClient
global_messenger: Messenger
global_args: SummarizePlanArgs
global_config: Config
global_server_started = False


def listen_for_updates(
    pco_client: PlanningCenterClient,
    messenger: Messenger,
    args: SummarizePlanArgs,
    config: Config,
) -> None:
    global global_pco_client, global_messenger, global_args, global_config, global_server_started
    global_pco_client = pco_client
    global_messenger = messenger
    global_args = args
    global_config = config

    # TODO: Change the closing message to clarify that this will stop the server?
    messenger.log_status(
        TaskStatus.RUNNING, f"Listening for changes on http://localhost:{args.port}."
    )
    global_server_started = True
    bottle.run(host="localhost", port=args.port, debug=True)


@bottle.get("/check-updates")
def _check_for_updates():  # pyright: ignore[reportUnusedFunction]
    prev_summary = lib.load_plan_summary(global_config.plan_summary_json_file)
    summary_changed = _generate_and_save_summary(
        pco_client=global_pco_client,
        messenger=global_messenger,
        args=global_args,
        config=global_config,
        prev_summary=prev_summary,
    )
    return {"changes": summary_changed}


def _stop_server():
    if global_server_started:
        my_pid = os.getpid()
        os.kill(my_pid, signal.SIGTERM)


def _generate_and_save_summary(
    pco_client: PlanningCenterClient,
    messenger: Messenger,
    args: SummarizePlanArgs,
    config: Config,
    prev_summary: Optional[PlanItemsSummary],
) -> bool:
    """
    Generate a summary of the current plan on Planning Center Online.
    Save HTML and JSON versions of the plan in the directory specified by
    `config`.
    Return `True` iff the new plan is different from the previous one.
    """
    if args.demo:
        summary = lib.load_plan_summary(_DEMO_FILE)
    else:
        summary = lib.get_plan_summary(
            client=pco_client,
            messenger=messenger,
            config=config,
            dt=config.start_time.date(),
        )

    config.plan_summary_html_file.parent.mkdir(parents=True, exist_ok=True)
    html = lib.plan_summary_to_html(summary)
    config.plan_summary_html_file.write_text(str(html), encoding="utf-8")
    json = lib.plan_summary_to_json(summary)
    config.plan_summary_json_file.write_text(json, encoding="utf-8")

    # TODO: Generate and save a diff so that the user can see what changed?
    return summary != prev_summary


if __name__ == "__main__":
    _args = SummarizePlanArgs.parse(sys.argv)
    _cfg = Config(_args)
    dependency_provider = ReccDependencyProvider(
        args=_args,
        config=_cfg,
        log_file=_cfg.summarize_plan_log,
        script_name="Summarize Plan",
        description=SummarizePlanArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    main(_args, _cfg, dependency_provider)
