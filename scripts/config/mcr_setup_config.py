from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable

from .config import Config
from .recc_args import ReccArgs


class McrSetupArgs(ReccArgs):
    NAME = "mcr_setup"
    DESCRIPTION = "This script will guide you through the steps to setting up the MCR visuals station for a Sunday gathering."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.show_browser = args.show_browser

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )
        return super().set_up_parser(parser)


class McrSetupConfig(Config):
    def __init__(self, args: McrSetupArgs, strict: bool = False) -> None:
        self._args = args
        super().__init__(args, strict)

    @property
    def message_notes_file(self) -> Path:
        return self.assets_by_service_dir.joinpath(self.message_notes_filename)

    @property
    def slide_blueprints_file(self) -> Path:
        return self.assets_by_service_dir.joinpath(self.blueprints_filename)

    def fill_placeholders(self, text: str) -> str:
        text = text.replace(
            "%{slides.message_notes}%", self.message_notes_file.as_posix()
        )
        text = text.replace(
            "%{slides.blueprints}%", self.slide_blueprints_file.as_posix()
        )
        return super().fill_placeholders(text)
