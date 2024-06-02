import dataclasses

from autochecklist import Messenger, TaskStatus


@dataclasses.dataclass
class RetryCounter:
    n: int = 0


def fail_then_succeed(msg: Messenger, cnt: RetryCounter) -> None:
    global n
    if cnt.n == 0:
        cnt.n += 1
        raise ValueError("Epic fail.")
    else:
        msg.log_status(TaskStatus.DONE, "Success!")
