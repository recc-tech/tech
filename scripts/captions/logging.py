import sys


class Colour:
    GREY = "\u001b[30;1m"
    YELLOW = "\u001b[33;1m"
    RED = "\u001b[31;1m"
    RESET = "\u001b[0m"


class Logger:
    @staticmethod
    def info(message: str) -> None:
        print(f"{Colour.GREY}{message}{Colour.RESET}")

    @staticmethod
    def warn(message: str) -> None:
        print(f"{Colour.YELLOW}{message}{Colour.RESET}")

    @staticmethod
    def error(message: str) -> None:
        sys.exit(f"{Colour.RED}{message}{Colour.RESET}")
