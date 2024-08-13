import sys
from argparse import ArgumentParser, Namespace
from enum import Enum
from typing import Callable, List

import autochecklist
import external_services
from args import ReccArgs
from autochecklist import TaskModel
from config import Config
from external_services import PlanningCenterClient
from lib import ReccDependencyProvider


class App(Enum):
    PLANNING_CENTER = "pco"


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
                    name="launch_pco",
                    description="Open Planning Center Online.",
                )
        tasks.append(t)
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=TaskModel(name="launch_apps", subtasks=tasks),
        module=sys.modules[__name__],
    )


def launch_pco(pco_client: PlanningCenterClient) -> None:
    plan = pco_client.find_plan_by_date(dt=config.start_time.date())
    external_services.launch_firefox(plan.web_page_url)


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
