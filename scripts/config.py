from datetime import datetime
from pathlib import Path
from typing import Union


class Config:
    """
    Central location for configuration information.
    """

    KEYRING_APP_NAME = "recc_tech_mcr_teardown"

    def __init__(self, home_dir: Path, message_series: str, message_title: str):
        self.home_dir = home_dir.resolve()
        self.message_series = message_series.strip()
        self.message_title = message_title.strip()

        date_ymd = datetime.now().strftime("%Y-%m-%d")
        self.captions_dir = self.home_dir.joinpath("Captions").joinpath(date_ymd)
        self.log_dir = self.home_dir.joinpath("Logs")

        self.vimeo_video_uri: Union[str, None] = None
        self.vimeo_video_texttracks_uri: Union[str, None] = None

    def fill_placeholders(self, text: str) -> str:
        text = (
            text.replace("%{DATE_MDY}%", datetime.now().strftime("%B %d, %Y"))
            .replace("%{DATE_YMD}%", datetime.now().strftime("%Y-%m-%d"))
            .replace("%{MESSAGE_SERIES}%", self.message_series)
            .replace("%{MESSAGE_TITLE}%", self.message_title)
            .replace("%{CAPTIONS_DIR}%", str(self.captions_dir))
        )

        if "%{" in text or "}%" in text:
            raise ValueError(f'Text "{text}" contains an unknown placeholder.')

        return text
