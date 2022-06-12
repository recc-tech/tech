import sys


class Logger:
    GREY = "\u001b[30;1m"
    YELLOW = "\u001b[33;1m"
    RED = "\u001b[31;1m"
    RESET = "\u001b[0m"

    @staticmethod
    def info(message: str) -> None:
        print(f"{Logger.GREY}{message}{Logger.RESET}")

    @staticmethod
    def warn(message: str) -> None:
        print(f"{Logger.YELLOW}{message}{Logger.RESET}")

    @staticmethod
    def error(message: str) -> None:
        sys.exit(f"{Logger.RED}{message}{Logger.RESET}")
