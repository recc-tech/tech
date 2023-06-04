from datetime import datetime
from pathlib import Path
from typing import Union


class Config:
    """
    Central location for configuration information.
    """

    def __init__(
        self,
        home_dir: Path,
        message_series: str,
        message_title: str,
        boxcast_event_id: str,
    ):
        self._home_dir = home_dir.resolve()
        self._message_series = message_series.strip()
        self._message_title = message_title.strip()
        self._boxcast_event_id = boxcast_event_id

        date_mdy = datetime.now().strftime("%B %d, %Y")
        self.live_event_title = f"Sunday Gathering LIVE: {date_mdy}"
        self.rebroadcast_title = f"Sunday Gathering Rebroadcast: {date_mdy}"
        self.rebroadcast_setup_url = f"https://dashboard.boxcast.com/#/new-event?streamSource=recording&sourceBroadcastId={self._boxcast_event_id}"
        self.live_event_url = f"https://dashboard.boxcast.com/#/events/{self._boxcast_event_id}"

        date_ymd = datetime.now().strftime("%Y-%m-%d")
        self.log_dir = self._home_dir.joinpath("Logs")

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
            text.replace("%{LIVE_EVENT_TITLE}%", self.live_event_title)
            .replace("%{REBROADCAST_TITLE}%", self.rebroadcast_title)
            .replace(
                "%{ORIGINAL_CAPTIONS_PATH}%", self.original_captions_path.as_posix()
            )
            .replace(
                "%{CAPTIONS_WITHOUT_WORSHIP_PATH}%",
                self.captions_without_worship_path.as_posix(),
            )
            .replace("%{FINAL_CAPTIONS_PATH}%", self.final_captions_path.as_posix())
        )

        if "%{" in text or "}%" in text:
            raise ValueError(f'Text "{text}" contains an unknown placeholder.')

        return text
