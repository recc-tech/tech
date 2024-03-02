from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from autochecklist import BaseArgs

from .parsing_helpers import parse_directory


# TODO: Move this to a different package?
class ReccArgs(BaseArgs):
    # TODO: Make the initialization more type-safe for testing purposes?
    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.home_dir: Optional[Path] = args.home_dir
        if self.home_dir is not None:
            self.home_dir = self.home_dir.resolve()
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
