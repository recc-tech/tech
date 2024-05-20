import sys

import autochecklist
from args import ReccArgs
from autochecklist import DependencyProvider, TaskModel
from config import Config


class MyService:
    pass


def missing_dependency(s: MyService) -> None:
    pass


def main(args: ReccArgs, config: Config, dep: DependencyProvider):
    tasks = TaskModel(
        "missing_dependency",
        description="The function for this task refers to a class which the DependencyProvider does not provide.",
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=tasks,
        module=sys.modules[__name__],
    )
