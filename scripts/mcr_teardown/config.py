from datetime import datetime
from pathlib import Path
from typing import Union

from autochecklist.base_config import BaseConfig


class McrTeardownConfig(BaseConfig):
    def __init__(
        self,
        home_dir: Path,
        downloads_dir: Path,
        message_series: str,
        message_title: str,
        boxcast_event_id: str,
    ):
        self._home_dir = home_dir.resolve()
        self._downloads_dir = downloads_dir.resolve()
        self._message_series = message_series.strip()
        self._message_title = message_title.strip()
        self._boxcast_event_id = boxcast_event_id

        date_mdy = BaseConfig._date_mdy(datetime.now())
        self.live_event_title = f"Sunday Gathering LIVE: {date_mdy}"
        self.live_event_url = (
            f"https://dashboard.boxcast.com/broadcasts/{self._boxcast_event_id}"
        )
        self.live_event_captions_tab_url = self.live_event_url + "?tab=captions"
        self.captions_download_path = self._downloads_dir.joinpath(
            f"{self._boxcast_event_id}_captions.vtt"
        )
        self.rebroadcast_title = f"Sunday Gathering Rebroadcast: {date_mdy}"
        self.rebroadcast_setup_url = f"https://dashboard.boxcast.com/#/new-event?streamSource=recording&sourceBroadcastId={self._boxcast_event_id}"
        self.boxcast_edit_captions_url = (
            f"https://dashboard.boxcast.com/#/caption-editor/{self._boxcast_event_id}"
        )

        log_dir = self._home_dir.joinpath("Logs")
        date_ymd = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H-%M-%S")
        self.log_file = log_dir.joinpath(f"{date_ymd} {current_time} mcr_teardown.log")

        self._captions_dir = self._home_dir.joinpath("Captions").joinpath(date_ymd)
        self.original_captions_path = self._captions_dir.joinpath("original.vtt")
        self.captions_without_worship_path = self._captions_dir.joinpath(
            "without_worship.vtt"
        )
        self.final_captions_path = self._captions_dir.joinpath("final.vtt")

        self.vimeo_video_title = (
            f"{date_ymd} | {self._message_series} | {self._message_title}"
        )
        self.vimeo_video_uri: Union[str, None] = None
        self.vimeo_video_texttracks_uri: Union[str, None] = None

    def fill_placeholders(self, text: str) -> str:
        text = (
            text.replace("%{REBROADCAST_TITLE}%", self.rebroadcast_title)
            .replace(
                "%{ORIGINAL_CAPTIONS_PATH}%", self.original_captions_path.as_posix()
            )
            .replace(
                "%{CAPTIONS_WITHOUT_WORSHIP_PATH}%",
                self.captions_without_worship_path.as_posix(),
            )
            .replace("%{FINAL_CAPTIONS_PATH}%", self.final_captions_path.as_posix())
            .replace("%{LOG_FILE}%", self.log_file.as_posix())
            .replace("%{VIMEO_VIDEO_TITLE}%", self.vimeo_video_title)
        )

        # Call the superclass' method *after* the subclass' method so that the check for unknown placeholders happens
        # at the end
        return super().fill_placeholders(text)
