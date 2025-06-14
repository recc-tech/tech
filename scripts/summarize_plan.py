import os
import signal
import sys
import time
import traceback
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import autochecklist
import bottle  # pyright: ignore[reportMissingTypeStubs]
import external_services
import lib
from args import ReccArgs
from autochecklist import Messenger, ProblemLevel, TaskModel, TaskStatus
from config import Config
from external_services import PlanningCenterClient
from lib import PlanSummary, ReccDependencyProvider, SimplifiedMessengerSettings

_DEMO_FILE_1 = Path(__file__).parent.joinpath(
    "test", "integration", "summarize_plan_data", "20240414_summary.json"
)
_DEMO_FILE_2 = Path(__file__).parent.joinpath(
    "test", "integration", "summarize_plan_data", "20240414_summary_edited.json"
)


class SummarizePlanArgs(ReccArgs):
    NAME = "summarize_plan"
    DESCRIPTION = "This script will generate a summary of the plan for today's service."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        self.no_open: bool = args.no_open
        self.demo: bool = args.demo
        self.port: int = args.port
        self.clean: bool = args.clean
        super().__init__(args, error)
        if self.clean:
            self.auto_close = True

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
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete all old plan summaries and exit.",
        )
        return super().set_up_parser(parser)


def main(args: SummarizePlanArgs, config: Config, dep: ReccDependencyProvider) -> None:
    tasks = TaskModel(
        "summarize_plan",
        description="An error occurred.",
        only_auto=True,
    )
    try:
        autochecklist.run(
            args=args,
            config=config,
            dependency_provider=dep,
            tasks=tasks,
            module=sys.modules[__name__],
        )
    finally:
        _stop_server()


# Use global variables to keep track of services (e.g., the
# `PlanningCenterClient` and `Messenger`).
# Maybe it's a bit gross, but other solutions (e.g., writing to a file or a
# database) would surely be more complex and might not work for services.
global_pco_client: PlanningCenterClient
global_messenger: Messenger
global_args: SummarizePlanArgs
global_config: Config
global_server_started = False


def summarize_plan(
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

    config.plan_summaries_dir.mkdir(exist_ok=True, parents=True)

    if args.clean:
        _delete_old_plan_summaries(config.plan_summaries_dir)
        return

    if args.demo:
        s = lib.load_plan_summary(_DEMO_FILE_1)
        _save_summary(s, config.plan_summaries_dir)
        messenger.log_problem(
            ProblemLevel.WARN,
            "The script is running in demo mode, so it will not check Planning Center."
            f" The plan will instead be loaded from {_DEMO_FILE_2.resolve().as_posix()}",
        )

    latest_summary_path = _find_latest_summary(config.plan_summaries_dir)
    if latest_summary_path is not None:
        messenger.log_status(
            TaskStatus.RUNNING,
            f"A plan summary already exists at {latest_summary_path.resolve().as_posix()}.",
        )
    else:
        summary = _generate_summary(
            pco_client=pco_client,
            messenger=messenger,
            args=args,
            config=config,
        )
        new_summary_path = _save_summary(summary, config.plan_summaries_dir)
        messenger.log_status(
            TaskStatus.RUNNING,
            f"Saved summary to {new_summary_path.resolve().as_posix()}.",
        )

    if not args.no_open:
        url = f"http://localhost:{args.port}/plan-summary.html"
        try:
            external_services.launch_firefox(url)
        except Exception as e:
            messenger.log_problem(
                ProblemLevel.WARN,
                f"Failed to open summary in Firefox: {e}.",
                traceback.format_exc(),
            )

    # The Bottle app logs requests to the terminal by default, which crashes
    # the app if it's running without a terminal
    with open(os.devnull, "w") as f:
        sys.stdout = sys.stderr = f

        messenger.log_status(
            TaskStatus.RUNNING,
            f"Listening for changes on http://localhost:{args.port}.",
        )
        global_server_started = True
        bottle.run(host="localhost", port=args.port, debug=True)


@bottle.hook("after_request")
def _enable_cors() -> None:  # pyright: ignore[reportUnusedFunction]
    bottle.response.headers["Access-Control-Allow-Origin"] = "*"


@bottle.post("/summaries")
def _check_for_updates() -> object:  # pyright: ignore[reportUnusedFunction]
    try:
        prev_summary_path = _find_latest_summary(global_config.plan_summaries_dir)
        prev_summary = (
            None
            if prev_summary_path is None
            else lib.load_plan_summary(prev_summary_path)
        )
        new_summary = _generate_summary(
            pco_client=global_pco_client,
            messenger=global_messenger,
            args=global_args,
            config=global_config,
        )
        changes = (
            True
            if prev_summary is None
            else lib.diff_plan_summaries(old=prev_summary, new=new_summary).plan_changed
        )
        if changes:
            _save_summary(new_summary, global_config.plan_summaries_dir)
        return {"changes": changes}
    except Exception as e:
        global_messenger.log_problem(
            ProblemLevel.ERROR,
            f"An error occurred while checking for updates: {e} ({type(e).__name__})",
        )
        raise


@bottle.get("/plan-summary.html")
def _get_summary_diff() -> str:  # pyright: ignore[reportUnusedFunction]
    try:
        old_summary_id = (
            bottle.request.query.old  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        )
        new_summary_path = _find_latest_summary(global_config.plan_summaries_dir)
        if new_summary_path is None:
            return f"No plan summaries have been generated yet (in {global_config.plan_summaries_dir.resolve().as_posix()})."
        if not old_summary_id:
            old_id = new_summary_path.stem
            bottle.redirect(f"/plan-summary.html?old={old_id}")
        new_summary = lib.load_plan_summary(new_summary_path)
        old_summary_path = (
            new_summary_path
            if old_summary_id == "latest"
            else global_config.plan_summaries_dir.joinpath(f"{old_summary_id}.json")
        )
        old_summary = lib.load_plan_summary(old_summary_path)
        diff = lib.diff_plan_summaries(old=old_summary, new=new_summary)
        old_plans = [
            (p.stem, _friendly_plan_name(p))
            for p in _list_existing_summaries(global_config.plan_summaries_dir)
        ]
        return lib.plan_summary_diff_to_html(
            diff,
            old_plans=old_plans,
            current_plan_id=old_summary_id,
            port=global_args.port,
        )
    except bottle.BottleException:
        # This is what redirect() raises, so it's probably not a problem
        raise
    except Exception as e:
        global_messenger.log_problem(
            ProblemLevel.ERROR,
            f"An error occurred while generating summary web page: {e} ({type(e).__name__})",
        )
        raise


def _stop_server():
    if global_server_started:
        my_pid = os.getpid()
        os.kill(my_pid, signal.SIGTERM)


def _generate_summary(
    pco_client: PlanningCenterClient,
    messenger: Messenger,
    args: SummarizePlanArgs,
    config: Config,
) -> PlanSummary:
    """
    Generate a summary of the current plan on Planning Center Online.
    """
    if args.demo:
        return lib.load_plan_summary(_DEMO_FILE_2)
    else:
        return lib.get_plan_summary(
            client=pco_client,
            messenger=messenger,
            config=config,
            dt=config.start_time.date(),
        )


def _save_summary(summary: PlanSummary, dir: Path) -> Path:
    choose_fname = lambda: f"{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    json_path = dir.joinpath(choose_fname())

    # Avoid overwriting a previous summary
    if json_path.exists():
        time.sleep(2)
        json_path = dir.joinpath(choose_fname())
    assert not json_path.exists()

    json_path.write_text(lib.plan_summary_to_json(summary))
    return json_path


def _friendly_plan_name(p: Path) -> str:
    id = p.stem
    assert len(id) == 14
    hour = id[8:10]
    minute = id[10:12]
    second = id[12:14]
    return f"{hour}:{minute}:{second}"


def _list_existing_summaries(dir: Path) -> List[Path]:
    today = datetime.now().strftime("%Y%m%d")
    time_pattern = "[0123456789]" * 6
    return sorted(dir.glob(f"{today}{time_pattern}.json"))


def _delete_old_plan_summaries(dir: Path) -> None:
    files = _list_existing_summaries(dir)
    for f in files:
        # It would be weird for the file to not exist, but why should it cause
        # the app to crash?
        f.unlink(missing_ok=True)


def _find_latest_summary(dir: Path) -> Optional[Path]:
    files = _list_existing_summaries(dir)
    return None if not files else files[-1]


if __name__ == "__main__":
    _args = SummarizePlanArgs.parse(sys.argv)
    _cfg = Config(_args)
    msg = SimplifiedMessengerSettings(
        log_file=_cfg.summarize_plan_log,
        script_name="Summarize Plan",
        description=SummarizePlanArgs.DESCRIPTION,
        show_statuses_by_default=True,
        confirm_exit_message="Stop checking for updates?",
    )
    dependency_provider = ReccDependencyProvider(
        args=_args, config=_cfg, messenger=msg, lazy_login=_args.demo
    )
    main(_args, _cfg, dependency_provider)
