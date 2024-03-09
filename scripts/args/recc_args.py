from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from autochecklist import BaseArgs

from .parsing_helpers import parse_directory


class ReccArgs(BaseArgs):
    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.start_time: datetime = (
            datetime.combine(args.date, datetime.now().time())
            if args.date
            else datetime.now()
        )

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        common_args = parser.add_argument_group("RECC common arguments")
        common_args.add_argument(
            "--home-dir",
            type=parse_directory,
            help="The home directory.",
        )
        common_args.add_argument(
            "--date",
            type=lambda x: datetime.strptime(x, "%Y-%m-%d").date(),
            help="Pretend the script is running on a different date.",
        )
        super().set_up_parser(parser)

    def get(self, key: str) -> Optional[object]:
        t = self.start_time
        root = Path(__file__).resolve().parent.parent.parent
        d = {
            "STARTUP_YMD": t.strftime("%Y-%m-%d"),
            "STARTUP_MDY": f"{t.strftime('%B')} {t.day}, {t.year}",
            "STARTUP_TIMESTAMP": t.strftime("%Y%m%d-%H%M%S"),
            # TODO: Move this to the Config class because it's not really
            # command-line argument-related
            "REPO_ROOT": str(root),
        }
        if key in d:
            return d[key]
        else:
            return super().get(key)