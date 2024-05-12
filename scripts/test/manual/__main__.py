import subprocess
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, List, Tuple

import summarize_plan
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
from external_services import BoxCastApiClient, CredentialStore, PlanningCenterClient
from summarize_plan import SummarizePlanArgs

_BROADCAST_ID = "on8bvqsbddurxkmhppld"
_REBROADCAST_TITLE = f"Test Rebroadcast {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
_VIMEO_TITLE = f"Test Video {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
_REBROADCAST_START = datetime.combine(
    date=datetime.now().date() + timedelta(days=1),
    time=time(hour=13, minute=3, second=14),
)
_CAPTIONS_PATH = Path(__file__).resolve().parent.joinpath("data", "captions.vtt")


class TestCase(Enum):
    RUN_GUI = "run_gui"
    CANCEL_GUI = "cancel_gui"
    REBROADCAST = "rebroadcast"
    CAPTIONS = "captions"
    VIMEO_EXPORT = "vimeo_export"
    PLAN_SUMMARY_20240414 = "plan_summary_20240414"
    PLAN_SUMMARY_20240505 = "plan_summary_20240505"


class ManualTestArgs(ReccArgs):
    NAME = "test_manually"
    DESCRIPTION = "This script will guide you through testing parts of the project for which fully automated testing is impractical."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.tests: List[TestCase] = (
            list(TestCase) if not args.test else [TestCase(t) for t in args.test]
        )
        self.coverage: bool = args.coverage

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--test",
            action="append",
            choices=[t.value for t in TestCase],
            help="Test cases to run (default: all of them)",
        )
        parser.add_argument(
            "--coverage",
            action="store_true",
            help="If this flag is provided, Python child processes will be run using coverage run --append instead of python.",
        )
        return super().set_up_parser(parser)


class ManualTestScript(Script[ManualTestArgs, Config]):
    def parse_args(self) -> ManualTestArgs:
        return ManualTestArgs.parse(sys.argv)

    def create_config(self, args: ReccArgs) -> Config:
        return Config(args)

    def create_messenger(self, args: ReccArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(config.schedule_rebroadcast_log)
        input_messenger = (
            TkMessenger(
                "Autochecklist",
                ManualTestArgs.DESCRIPTION,
                theme=config.ui_theme,
                show_statuses_by_default=True,
            )
            if args.ui == "tk"
            else ConsoleMessenger(
                ManualTestArgs.DESCRIPTION, show_task_status=args.verbose
            )
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, args: ManualTestArgs, config: Config, messenger: Messenger
    ) -> Tuple[TaskModel, FunctionFinder]:
        credential_store = CredentialStore(messenger=messenger)
        boxcast_client = BoxCastApiClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            lazy_login=True,
        )
        pco_client = PlanningCenterClient(
            messenger=messenger,
            credential_store=credential_store,
            config=config,
            lazy_login=True,
        )
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[boxcast_client, pco_client, messenger, config, args],
            messenger=messenger,
        )
        task_model = _make_task_model(args.tests)
        return task_model, function_finder


def _make_task_model(cases: List[TestCase]) -> TaskModel:
    tasks = [
        TaskModel(
            name="ready",
            description="Press 'Done' once you are ready to start testing.",
        ),
    ]
    latest_task = "ready"
    if TestCase.RUN_GUI in cases:
        t = TaskModel(
            name="test_run_GUI",
            subtasks=[
                TaskModel(
                    name="ready_run_GUI",
                    description=(
                        "The next task will open a separate GUI window."
                        " Follow the instructions on that window and check that the GUI itself works as expected."
                    ),
                ),
                TaskModel(
                    name="run_GUI",
                    description="Run the GUI and see if it works.",
                    only_auto=True,
                    prerequisites={"ready_run_GUI"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
    if TestCase.CANCEL_GUI in cases:
        t = TaskModel(
            name="test_cancel_GUI",
            subtasks=[
                TaskModel(
                    name="ready_cancel_GUI",
                    description=(
                        "The next task will open a separate GUI window."
                        " Complete one or two tasks and then close the window without completing the test."
                    ),
                ),
                TaskModel(
                    name="cancel_GUI",
                    description="Run the GUI and see if closing it early works.",
                    only_auto=True,
                    prerequisites={"ready_cancel_GUI"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
    if TestCase.REBROADCAST in cases:
        t = TaskModel(
            name="test_schedule_rebroadcast",
            subtasks=[
                TaskModel(
                    name="ready_schedule_rebroadcast",
                    description=(
                        f"The next task should create a broadcast called '{_REBROADCAST_TITLE}' starting at {_REBROADCAST_START.strftime('%Y-%m-%d %H:%M:%S')}."
                        + f" [IMPORTANT] Log in to BoxCast using the owner account before continuing."
                    ),
                ),
                TaskModel(
                    name="schedule_rebroadcast",
                    description="Failed to schedule rebroadcast.",
                    only_auto=True,
                    prerequisites={"ready_schedule_rebroadcast"},
                ),
                TaskModel(
                    name="delete_rebroadcast",
                    description="Go to BoxCast, check that the rebroadcast was created properly, and then delete it.",
                    prerequisites={"schedule_rebroadcast"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
    if TestCase.CAPTIONS in cases:
        t = TaskModel(
            name="test_update_captions",
            subtasks=[
                TaskModel(
                    name="ready_update_captions",
                    description="The next task should download captions and reupload them to BoxCast.",
                ),
                TaskModel(
                    name="download_captions",
                    description="Download captions",
                    only_auto=True,
                    prerequisites={"ready_update_captions"},
                ),
                TaskModel(
                    name="tweak_captions",
                    description=f"Tweak the captions in {_CAPTIONS_PATH.as_posix()} so that you'll be able to recognize the difference when re-uploaded.",
                    prerequisites={"download_captions"},
                ),
                TaskModel(
                    name="upload_captions",
                    description="Upload captions",
                    only_auto=True,
                    prerequisites={"tweak_captions"},
                ),
                TaskModel(
                    name="check_captions",
                    description=f"Check that the captions were uploaded properly (https://dashboard.boxcast.com/broadcasts/{_BROADCAST_ID}?tab=captions).",
                    prerequisites={"upload_captions"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
    if TestCase.VIMEO_EXPORT in cases:
        t = TaskModel(
            name="test_Vimeo_export",
            subtasks=[
                TaskModel(
                    name="ready_Vimeo_export",
                    description=(
                        "The next task should export a video to Vimeo."
                        f" [IMPORTANT] Log in to Vimeo before continuing."
                    ),
                ),
                TaskModel(
                    name="export_to_Vimeo",
                    description="Export to Vimeo.",
                    only_auto=True,
                    prerequisites={"ready_Vimeo_export"},
                ),
                TaskModel(
                    name="delete_Vimeo_export",
                    description="Check that the video was exported to Vimeo and then delete it.",
                    prerequisites={"export_to_Vimeo"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
    if TestCase.PLAN_SUMMARY_20240414 in cases:
        t = TaskModel(
            name="test_summarize_plan_20240414",
            subtasks=[
                TaskModel(
                    name="ready_summarize_plan_20240414",
                    description="The next task should show a summary of the plan from April 14, 2024.",
                ),
                TaskModel(
                    name="summarize_plan_20240414",
                    description="Show a summary of the plan from April 14, 2024.",
                    only_auto=True,
                    prerequisites={"ready_summarize_plan_20240414"},
                ),
                TaskModel(
                    name="check_plan_summary_20240414",
                    description="Check that the plan summary looks good.",
                    prerequisites={"summarize_plan_20240414"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
    if TestCase.PLAN_SUMMARY_20240505 in cases:
        t = TaskModel(
            name="test_summarize_plan_20240505",
            subtasks=[
                TaskModel(
                    name="ready_summarize_plan_20240505",
                    description="The next task should show a summary of the plan from May 5, 2024.",
                ),
                TaskModel(
                    name="summarize_plan_20240505",
                    description="Show a summary of the plan from May 5, 2024.",
                    only_auto=True,
                    prerequisites={"ready_summarize_plan_20240505"},
                ),
                TaskModel(
                    name="check_plan_summary_20240505",
                    description="Check that the plan summary looks good.",
                    prerequisites={"summarize_plan_20240505"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
    return TaskModel(name="test_manually", subtasks=tasks)


def run_GUI(args: ManualTestArgs) -> None:
    # Run in a separate process because having multiple GUIs open in the same
    # Python process is not supported (and not normally needed anyway)
    cmd = ["coverage", "run", "--append"] if args.coverage else ["python"]
    subprocess.run(cmd + ["-m", "autochecklist"])


def cancel_GUI(args: ManualTestArgs) -> None:
    # Run in a separate process because having multiple GUIs open in the same
    # Python process is not supported (and not normally needed anyway)
    cmd = ["coverage", "run", "--append"] if args.coverage else ["python"]
    subprocess.run(cmd + ["-m", "autochecklist"])


def schedule_rebroadcast(client: BoxCastApiClient) -> None:
    client.schedule_rebroadcast(
        broadcast_id=_BROADCAST_ID, name=_REBROADCAST_TITLE, start=_REBROADCAST_START
    )


def download_captions(client: BoxCastApiClient) -> None:
    client.download_captions(broadcast_id=_BROADCAST_ID, path=_CAPTIONS_PATH)


def upload_captions(client: BoxCastApiClient) -> None:
    client.upload_captions(broadcast_id=_BROADCAST_ID, path=_CAPTIONS_PATH)


def export_to_Vimeo(client: BoxCastApiClient, config: Config) -> None:
    client.export_to_vimeo(
        broadcast_id=_BROADCAST_ID,
        vimeo_user_id=config.vimeo_user_id,
        title=f"{_VIMEO_TITLE} (BoxCast ID {_BROADCAST_ID})",
    )


def summarize_plan_20240414(client: PlanningCenterClient, messenger: Messenger) -> None:
    args = SummarizePlanArgs.parse(["", "--date", "2024-04-14"])
    cfg = Config(args=args, allow_multiple_only_for_testing=True)
    summarize_plan.summarize_plan(
        pco_client=client,
        args=args,
        config=cfg,
        messenger=messenger,
    )


def summarize_plan_20240505(client: PlanningCenterClient, messenger: Messenger) -> None:
    args = SummarizePlanArgs.parse(["", "--date", "2024-05-05"])
    cfg = Config(args=args, allow_multiple_only_for_testing=True)
    summarize_plan.summarize_plan(
        pco_client=client,
        args=args,
        config=cfg,
        messenger=messenger,
    )


if __name__ == "__main__":
    ManualTestScript().run()