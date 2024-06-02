import dataclasses

from autochecklist import Messenger, TaskStatus


@dataclasses.dataclass
class Foo:
    x: int


def A(msg: Messenger, f: Foo) -> None:
    msg.log_status(TaskStatus.RUNNING, f"Running A with x = {f.x}")


def B(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running B")


def C(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running C")


def D(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running D")


def E(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "Running E")
