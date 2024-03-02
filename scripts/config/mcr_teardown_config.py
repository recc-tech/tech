import re
import typing
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from typing import Callable, List

from .config import Config
from .parsing_helpers import parse_non_empty_string
from .recc_args import ReccArgs


# TODO: Move stuff like this to a separate `args` package
class McrTeardownArgs(ReccArgs):
    NAME = "mcr_teardown"
    DESCRIPTION = "This script will guide you through the steps to shutting down the MCR video station after a Sunday gathering."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)

        if args.boxcast_event_url:
            args.boxcast_event_id = args.boxcast_event_url
        # For some reason Pylance complains about the del keyword but not delattr
        delattr(args, "boxcast_event_url")
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
        # TODO: Check that all args (incl. other scripts) have reasonable
        # (usually no) defaults
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

        boxcast_event_id_group = parser.add_mutually_exclusive_group()
        boxcast_event_id_group.add_argument(
            "-b",
            "--boxcast-event-url",
            type=parse_boxcast_event_url,
            help="URL of today's live event on BoxCast. For example, https://dashboard.boxcast.com/broadcasts/abcdefghijklm0123456.",
        )
        boxcast_event_id_group.add_argument(
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


class McrTeardownConfig(Config):
    def __init__(self, args: McrTeardownArgs, strict: bool = False) -> None:
        self._args = args
        super().__init__(args, strict)

    @property
    def live_event_url(self) -> str:
        return self.live_event_url_template.fill(
            {"BOXCAST_EVENT_ID": self._args.boxcast_event_id}
        )

    @property
    def live_event_captions_tab_url(self) -> str:
        return self.live_event_captions_tab_url_template.fill(
            {"BOXCAST_EVENT_ID": self._args.boxcast_event_id}
        )

    @property
    def boxcast_edit_captions_url(self) -> str:
        return self.boxcast_edit_captions_url_template.fill(
            {"BOXCAST_EVENT_ID": self._args.boxcast_event_id}
        )

    @property
    def rebroadcast_setup_url(self) -> str:
        return self.rebroadcast_setup_url_template.fill(
            {"BOXCAST_EVENT_ID": self._args.boxcast_event_id}
        )

    @property
    def captions_download_path(self) -> Path:
        return Path(
            self.captions_download_path_template.fill(
                {"BOXCAST_EVENT_ID": self._args.boxcast_event_id}
            )
        )

    @property
    def vimeo_video_title(self) -> str:
        return self.vimeo_video_title_template.fill(
            {
                "SERIES_TITLE": self._args.message_series,
                "MESSAGE_TITLE": self._args.message_title,
            }
        )


def parse_boxcast_event_url(event_url: str) -> str:
    if not event_url:
        raise ArgumentTypeError("Empty input. The event URL is required.")
    if all(c == "\x16" for c in event_url):
        raise ArgumentTypeError(
            "You entered the value CTRL+V, which is not a valid event URL. Try right-clicking to paste."
        )

    # The event URL should be in the form "https://dashboard.boxcast.com/broadcasts/<EVENT-ID>"
    # Allow a trailing forward slash just in case
    event_url = event_url.strip()
    regex = "^https://dashboard\\.boxcast\\.com/broadcasts/([a-zA-Z0-9]{20,20})/?(?:\\?.*)?$"
    pattern = re.compile(regex)
    regex_match = pattern.search(event_url)
    if not regex_match:
        raise ArgumentTypeError(
            f"Expected the BoxCast event URL to match the regular expression '{regex}', but received '{event_url}'. Are you sure you copied the URL correctly? If you think there is a problem with the script, try entering the BoxCast event ID directly instead."
        )
    event_id = regex_match.group(1)
    return event_id
