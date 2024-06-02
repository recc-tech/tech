import autochecklist
from args import ReccArgs
from autochecklist import DependencyProvider, TaskModel
from config import Config


def main(args: ReccArgs, config: Config, dep: DependencyProvider):
    tasks = TaskModel(
        "broken_task_graph",
        description="The prerequisite for this task does not exist",
        prerequisites={"missing"},
    )
    autochecklist.run(
        args=args, config=config, dependency_provider=dep, tasks=tasks, module=None
    )
