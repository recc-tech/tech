import typing
from argparse import ArgumentParser, Namespace
from typing import Callable, List

from .parsing_helpers import parse_non_empty_string
from .recc_args import ReccArgs


class McrTeardownArgs(ReccArgs):
    NAME = "mcr_teardown"
    DESCRIPTION = "This script will guide you through the steps to shutting down the MCR video station after a Sunday gathering."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)

        if args.auto is not None:
            if "none" in args.auto and len(args.auto) > 1:
                error("If 'none' is included in --auto, it must be the only value.")
            if args.auto == ["none"]:
                args.auto = typing.cast(List[str], [])

        self.message_series: str = args.message_series or ""
        self.message_title: str = args.message_title or ""
        self.boxcast_event_id: str = args.boxcast_event_id or ""
        self.lazy_login: bool = args.lazy_login
        self.show_browser: bool = args.show_browser

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-s",
            "--message-series",
            type=parse_non_empty_string,
            help="Name of the series to which today's sermon belongs.",
        )
        parser.add_argument(
            "-t",
            "--message-title",
            type=parse_non_empty_string,
            help="Title of today's sermon.",
        )
        parser.add_argument(
            "--boxcast-event-id",
            type=parse_non_empty_string,
            help='ID of today\'s live event on BoxCast. For example, in the URL https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456, the event ID is "abcdefghijklm0123456" (without the quotation marks).',
        )

        debug_args = parser.add_argument_group("Debug arguments")
        debug_args.add_argument(
            "--lazy-login",
            action="store_true",
            help="If this flag is provided, then the script will not immediately log in to services like Vimeo and BoxCast. Instead, it will wait until that particular service is specifically requested.",
        )
        debug_args.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )

        return super().set_up_parser(parser)
