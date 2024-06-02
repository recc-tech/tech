from autochecklist import Messenger, TaskStatus


def cancel(msg: Messenger) -> None:
    token = msg.allow_cancel()
    token.cancel()
    token.raise_if_cancelled()


def foo(msg: Messenger) -> None:
    msg.log_status(TaskStatus.RUNNING, "foo running as usual.")
