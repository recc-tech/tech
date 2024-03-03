from pathlib import Path

from args import McrTeardownArgs

from .config import Config


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

    def fill_placeholders(self, text: str) -> str:
        text = text.replace("%{boxcast.live_event_url}%", self.live_event_url)
        text = text.replace(
            "%{boxcast.live_event_captions_tab_url}%", self.live_event_captions_tab_url
        )
        text = text.replace(
            "%{boxcast.edit_captions_url}%", self.boxcast_edit_captions_url
        )
        text = text.replace(
            "%{boxcast.rebroadcast_setup_url}%", self.rebroadcast_setup_url
        )
        text = text.replace(
            "%{boxcast.captions_download_path}%", self.captions_download_path.as_posix()
        )
        text = text.replace("%{vimeo.video_title}%", self.vimeo_video_title)
        return super().fill_placeholders(text)
