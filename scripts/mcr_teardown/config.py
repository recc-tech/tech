from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional

from common import ReccConfig


class McrTeardownConfig(ReccConfig):
    def __init__(
        self,
        message_series: str,
        message_title: str,
        boxcast_event_id: str,
        home_dir: Path,
        downloads_dir: Path,
        lazy_login: bool,
        now: datetime,
        show_browser: bool,
        ui: Literal["console", "tk"],
        verbose: bool,
        no_run: bool,
    ):
        super().__init__(
            home_dir=home_dir, now=now, ui=ui, verbose=verbose, no_run=no_run
        )

        self._downloads_dir = downloads_dir.resolve()
        self.lazy_login = lazy_login
        self.show_browser = show_browser
        self.message_series = message_series.strip()
        self.message_title = message_title.strip()
        self.boxcast_event_id = boxcast_event_id

        self.vimeo_video_uri: Optional[str] = None
        self.vimeo_video_texttracks_uri: Optional[str] = None

    @property
    def live_event_title(self) -> str:
        return f"Sunday Gathering LIVE: {_format_mdy(self.now)}"

    @property
    def live_event_url(self) -> str:
        return f"https://dashboard.boxcast.com/broadcasts/{self.boxcast_event_id}"

    @property
    def live_event_captions_tab_url(self) -> str:
        return f"{self.live_event_url}?tab=captions"

    @property
    def captions_download_path(self):
        return self._downloads_dir.joinpath(f"{self.boxcast_event_id}_captions.vtt")

    @property
    def rebroadcast_title(self) -> str:
        return f"Sunday Gathering Rebroadcast: {_format_mdy(self.now)}"

    @property
    def rebroadcast_setup_url(self) -> str:
        return f"https://dashboard.boxcast.com/schedule/broadcast?streamSource=recording&sourceBroadcastId={self.boxcast_event_id}"

    @property
    def boxcast_edit_captions_url(self) -> str:
        return f"https://dashboard.boxcast.com/broadcasts/{self.boxcast_event_id}/edit-captions"

    @property
    def log_file(self) -> Path:
        return self.log_dir.joinpath(
            f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')} mcr_teardown.log"
        ).resolve()

    @property
    def _captions_dir(self) -> Path:
        return self.home_dir.joinpath("Captions").joinpath(
            self.now.strftime("%Y-%m-%d")
        )

    @property
    def original_captions_path(self) -> Path:
        return self._captions_dir.joinpath("original.vtt")

    @property
    def final_captions_path(self) -> Path:
        return self._captions_dir.joinpath("final.vtt")

    @property
    def vimeo_video_title(self) -> str:
        return f"{self.now.strftime('%Y-%m-%d')} | {self.message_series} | {self.message_title}"

    def fill_placeholders(self, text: str) -> str:
        text = (
            text.replace("%{REBROADCAST_TITLE}%", self.rebroadcast_title)
            .replace(
                "%{ORIGINAL_CAPTIONS_PATH}%", self.original_captions_path.as_posix()
            )
            .replace("%{FINAL_CAPTIONS_PATH}%", self.final_captions_path.as_posix())
            .replace("%{LOG_FILE}%", self.log_file.as_posix())
            .replace("%{VIMEO_VIDEO_TITLE}%", self.vimeo_video_title)
        )

        # Call the superclass' method *after* the subclass' method so that the check for unknown placeholders happens
        # at the end
        return super().fill_placeholders(text)


def _format_mdy(dt: date) -> str:
    """
    Return the given date as a string in month day year format. The day of the month will not have a leading zero.

    Examples:
        - `_date_mdy(date(year=2023, month=6, day=4)) == 'June 4, 2023'`
        - `_date_mdy(date(year=2023, month=6, day=11)) == 'June 11, 2023'`
    """
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
