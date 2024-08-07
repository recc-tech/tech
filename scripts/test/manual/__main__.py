import subprocess
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Callable, List

import autochecklist
import summarize_plan
from args import ReccArgs
from autochecklist import Messenger, TaskModel, TaskStatus
from config import Config
from external_services import BoxCastApiClient, PlanningCenterClient
from lib import ReccDependencyProvider
from summarize_plan import SummarizePlanArgs

_BROADCAST_ID = "on8bvqsbddurxkmhppld"
_REBROADCAST_TITLE = f"Test Rebroadcast {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
_VIMEO_TITLE = f"Test Video {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (BoxCast ID {_BROADCAST_ID})"
_REBROADCAST_START = datetime.combine(
    date=datetime.now().date() + timedelta(days=1),
    time=time(hour=13, minute=3, second=14),
)


class TestCase(Enum):
    RELOAD_CONFIG_ERROR = "reload_config_error"
    RELOAD_CONFIG = "reload_config"
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


def _make_task_model(cases: List[TestCase]) -> TaskModel:
    tasks = [
        TaskModel(
            name="ready",
            description="Press 'Done' once you are ready to start testing.",
        ),
    ]
    latest_task = "ready"
    if TestCase.RELOAD_CONFIG_ERROR in cases:
        t = TaskModel(
            name="test_reload_config_error",
            subtasks=[
                TaskModel(
                    name="ready_reload_config_error",
                    description="The next task will test what happens when there's an error while reloading the config.",
                ),
                TaskModel(
                    name="display_old_ui_theme",
                    description="Failed to display old value of ui.theme.",
                    only_auto=True,
                    prerequisites={"ready_reload_config_error"},
                ),
                TaskModel(
                    name="change_config_0",
                    description="In config.toml, change the value of ui.theme and then make a breaking change somewhere else.",
                    prerequisites={"display_old_ui_theme"},
                ),
                TaskModel(
                    name="reload_config_error",
                    description="Press 'Reload Config'.",
                    prerequisites={"change_config_0"},
                ),
                TaskModel(
                    name="display_new_ui_theme",
                    description="Failed to display new value of ui.theme.",
                    only_auto=True,
                    prerequisites={"reload_config_error"},
                ),
                TaskModel(
                    name="check_reload_config_error",
                    description=(
                        "Check that the value of ui.theme has [[styled|emph|not]] changed and then undo all config changes."
                        " The value of ui.theme should be displayed in the task status section."
                    ),
                    prerequisites={"display_new_ui_theme"},
                ),
            ],
            prerequisites={"ready"},
        )
        tasks.append(t)
        latest_task = t.name
    if TestCase.RELOAD_CONFIG in cases:
        t = TaskModel(
            name="test_reload_config",
            subtasks=[
                TaskModel(
                    name="ready_reload_config",
                    description="The next task will test successfully reloading the config.",
                ),
                TaskModel(
                    name="display_old_vMix_URL",
                    description="Failed to display the old vMix URL.",
                    only_auto=True,
                    prerequisites={"ready_reload_config"},
                ),
                TaskModel(
                    name="change_config",
                    description="Change the vMix base URL in config.toml.",
                    prerequisites={"display_old_vMix_URL"},
                ),
                TaskModel(
                    name="reload_config",
                    description="Press 'Reload Config'.",
                    prerequisites={"change_config"},
                ),
                TaskModel(
                    name="display_new_vMix_URL",
                    description="Failed to display the new vMix URL.",
                    only_auto=True,
                    prerequisites={"reload_config"},
                ),
                TaskModel(
                    name="check_reload_config",
                    description="Check that the new value is correct, then undo the config change.",
                    prerequisites={"display_new_vMix_URL"},
                ),
            ],
            prerequisites={latest_task},
        )
        tasks.append(t)
        latest_task = t.name
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
            name="test_captions_workflow",
            subtasks=[
                TaskModel(
                    name="ready_captions_workflow",
                    description="The next task will walk you through the captions workflow using the 2024-07-28 broadcast.",
                ),
                TaskModel(
                    name="follow_captions_workflow",
                    description="Go through the full captions workflow.",
                    prerequisites={"ready_update_captions"},
                    only_auto=True,
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


def display_old_ui_theme(messenger: Messenger, config: Config) -> None:
    messenger.log_status(TaskStatus.DONE, f"Old UI theme: {config.ui_theme}")


def display_new_ui_theme(messenger: Messenger, config: Config) -> None:
    messenger.log_status(TaskStatus.DONE, f"New UI theme: {config.ui_theme}")


def display_old_vMix_URL(messenger: Messenger, config: Config) -> None:
    messenger.log_status(TaskStatus.DONE, f"Old vMix URL: {config.vmix_base_url}")


def display_new_vMix_URL(messenger: Messenger, config: Config) -> None:
    messenger.log_status(TaskStatus.DONE, f"New vMix URL: {config.vmix_base_url}")


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


def follow_captions_workflow() -> None:
    # Run in a separate process because having multiple GUIs open in the same
    # Python process is not supported (and not normally needed anyway)
    cmd = ["coverage", "run", "--append"] if args.coverage else ["python"]
    subprocess.run(cmd + ["-m", "test.manual.captions_workflow_20240728"])


def export_to_Vimeo(client: BoxCastApiClient, config: Config) -> None:
    client.export_to_vimeo(
        broadcast_id=_BROADCAST_ID,
        vimeo_user_id=config.vimeo_user_id,
        title=_VIMEO_TITLE,
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
    args = ManualTestArgs.parse(sys.argv)
    config = Config(args)
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.manual_test_log,
        script_name="Manual Test",
        description=ManualTestArgs.DESCRIPTION,
        show_statuses_by_default=True,
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dependency_provider,
        tasks=_make_task_model(args.tests),
        module=sys.modules[__name__],
    )
