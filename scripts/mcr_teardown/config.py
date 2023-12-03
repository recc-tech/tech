from datetime import datetime
from pathlib import Path
from typing import Union

from autochecklist import BaseConfig


class McrTeardownConfig(BaseConfig):
    def __init__(
        self,
        home_dir: Path,
        downloads_dir: Path,
        message_series: str = "",
        message_title: str = "",
        boxcast_event_id: str = "",
    ):
        self._home_dir = home_dir.resolve()
        self._downloads_dir = downloads_dir.resolve()
        self.message_series = message_series.strip()
        self.message_title = message_title.strip()
        self.boxcast_event_id = boxcast_event_id

        self.vimeo_video_uri: Union[str, None] = None
        self.vimeo_video_texttracks_uri: Union[str, None] = None

        now = datetime.now()
        self._start_date_ymd = now.strftime("%Y-%m-%d")
        self._start_date_mdy = BaseConfig._date_mdy(now)
        self._start_time = now.strftime("%H-%M-%S")

    @property
    def live_event_title(self) -> str:
        return f"Sunday Gathering LIVE: {self._start_date_mdy}"

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
        return f"Sunday Gathering Rebroadcast: {self._start_date_mdy}"

    @property
    def rebroadcast_setup_url(self) -> str:
        return f"https://dashboard.boxcast.com/schedule/broadcast?streamSource=recording&sourceBroadcastId={self.boxcast_event_id}"

    @property
    def boxcast_edit_captions_url(self) -> str:
        return f"https://dashboard.boxcast.com/broadcasts/{self.boxcast_event_id}/edit-captions"

    @property
    def log_dir(self) -> Path:
        return self._home_dir.joinpath("Logs")

    @property
    def log_file(self) -> Path:
        return self.log_dir.joinpath(
            f"{self._start_date_ymd} {self._start_time} mcr_teardown.log"
        ).resolve()

    @property
    def _captions_dir(self) -> Path:
        return self._home_dir.joinpath("Captions").joinpath(self._start_date_ymd)

    @property
    def original_captions_path(self) -> Path:
        return self._captions_dir.joinpath("original.vtt")

    @property
    def final_captions_path(self) -> Path:
        return self._captions_dir.joinpath("final.vtt")

    @property
    def vimeo_video_title(self) -> str:
        return f"{self._start_date_ymd} | {self.message_series} | {self.message_title}"

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
