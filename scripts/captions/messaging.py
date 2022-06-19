from enum import Enum

import sys


class Colour(Enum):
    GREY = "\u001b[30;1m"
    YELLOW = "\u001b[33;1m"
    RED = "\u001b[31;1m"
    RESET = "\u001b[0m"


class Messenger:
    @staticmethod
    def colour(message: str, col: Colour) -> str:
        return f"{col.value}{message}{Colour.RESET.value}"

    @classmethod
    def warn(cls, message: str, end: str = "\n") -> None:
        print(cls.colour(message, Colour.YELLOW), end=end)

    @classmethod
    def error(cls, message: str, end: str = "\n") -> None:
        print(cls.colour(message, Colour.RED), end=end)

    @classmethod
    def fatal(cls, message: str, end: str = "\n") -> None:
        cls.error(message, end)
        sys.exit(1)
