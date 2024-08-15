import os
import sys
from argparse import ArgumentParser, Namespace
from enum import Enum
from pathlib import Path
from typing import Callable, List

import autochecklist
import external_services
from args import ReccArgs
from autochecklist import TaskModel
from config import Config
from external_services import IssueType, PlanningCenterClient
from lib import ReccDependencyProvider


class App(Enum):
    PLANNING_CENTER = "pco"
    FOH_SETUP_CHECKLIST = "foh_setup_checklist"
    MCR_SETUP_CHECKLIST = "mcr_setup_checklist"
    MCR_TEARDOWN_CHECKLIST = "mcr_teardown_checklist"
    VMIX = "vmix"


class LaunchAppsArgs(ReccArgs):
    NAME = "launch_apps"
    DESCRIPTION = (
        "Launch apps or websites that will be used before or during the service."
    )

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.apps: List[App] = args.apps

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument("apps", nargs="+", type=App)
        return super().set_up_parser(parser)


def main(args: LaunchAppsArgs, config: Config, dep: ReccDependencyProvider) -> None:
    tasks: List[TaskModel] = []
    for app in args.apps:
        match app:
            case App.PLANNING_CENTER:
                t = TaskModel(
                    name="launch_PCO",
                    description="Open Planning Center Online.",
                )
            case App.FOH_SETUP_CHECKLIST:
                t = TaskModel(
                    name="open_FOH_setup_checklist",
                    description="Open the FOH setup checklist on GitHub.",
                )
            case App.MCR_SETUP_CHECKLIST:
                t = TaskModel(
                    name="open_MCR_setup_checklist",
                    description="Open the MCR setup checklist on GitHub.",
                )
            case App.MCR_TEARDOWN_CHECKLIST:
                t = TaskModel(
                    name="open_MCR_teardown_checklist",
                    description="Open the MCR teardown checklist on GitHub.",
                )
            case App.VMIX:
                t = TaskModel(
                    name="open_vMix",
                    description="Open last week's preset in vMix.",
                )
        tasks.append(t)
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=TaskModel(name="launch_apps", subtasks=tasks),
        module=sys.modules[__name__],
    )


# TODO: Get rid of the "unused function" warnings!


def launch_PCO(pco_client: PlanningCenterClient) -> None:
    plan = pco_client.find_plan_by_date(dt=config.start_time.date())
    external_services.launch_firefox(plan.web_page_url)


def open_FOH_setup_checklist(config: Config) -> None:
    issue = external_services.find_latest_github_issue(IssueType.FOH_SETUP, config)
    external_services.launch_firefox(issue.html_url)


def open_MCR_setup_checklist(config: Config) -> None:
    issue = external_services.find_latest_github_issue(IssueType.MCR_SETUP, config)
    external_services.launch_firefox(issue.html_url)


def open_MCR_teardown_checklist(config: Config) -> None:
    issue = external_services.find_latest_github_issue(IssueType.MCR_TEARDOWN, config)
    external_services.launch_firefox(issue.html_url)


def open_vMix(config: Config) -> None:
    preset = _get_latest_file(config.vmix_preset_dir)
    external_services.launch_vmix(preset)


def _get_latest_file(dir: Path) -> Path:
    return max(dir.glob("*.vmix"), key=os.path.getmtime)


if __name__ == "__main__":
    args = LaunchAppsArgs.parse(sys.argv)
    config = Config(args)
    dep = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.launch_apps_log,
        script_name=LaunchAppsArgs.NAME,
        description=LaunchAppsArgs.DESCRIPTION,
        show_statuses_by_default=False,
    )
    main(args, config, dep)
