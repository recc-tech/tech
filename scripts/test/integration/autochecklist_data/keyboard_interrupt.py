from autochecklist import Messenger, ProblemLevel


def keyboard_interrupt() -> None:
    raise KeyboardInterrupt()


def never_call_this(msg: Messenger) -> None:
    msg.log_problem(ProblemLevel.ERROR, "This task should never have been called!")
