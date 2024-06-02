import sys

import autochecklist
from args import ReccArgs
from autochecklist import DependencyProvider, TaskModel
from config import Config


def unused() -> None:
    pass


def foo() -> None:
    pass


def main(args: ReccArgs, config: Config, dep: DependencyProvider):
    tasks = TaskModel(
        "foo",
        description="There is an unused function in this file.",
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=tasks,
        module=sys.modules[__name__],
    )
