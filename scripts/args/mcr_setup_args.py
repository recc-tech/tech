from argparse import ArgumentParser, Namespace
from typing import Callable

from .recc_args import ReccArgs


class McrSetupArgs(ReccArgs):
    NAME = "mcr_setup"
    DESCRIPTION = "This script will guide you through the steps to setting up the MCR visuals station for a Sunday gathering."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.show_browser = args.show_browser

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        # TODO: Is this needed anymore?
        parser.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )
        return super().set_up_parser(parser)
