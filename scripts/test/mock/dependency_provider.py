from typing import List, Type

from autochecklist import DependencyProvider, Messenger, TaskStatus


class FixedDependencyProvider(DependencyProvider):
    def __init__(self, messenger: Messenger, args: List[object]) -> None:
        self.messenger = messenger
        self.args = args
        if messenger not in self.args:
            self.args.append(messenger)

    def get(self, typ: Type[object]) -> object:
        for a in self.args:
            if isinstance(a, typ):
                return a
        raise ValueError("No matching argument found.")

    def shut_down(self) -> None:
        self.messenger.log_status(
            TaskStatus.RUNNING,
            "Shut down.",
            task_name="dependency_provider",
        )
