from typing import Optional

from args import McrTeardownArgs

from .config import Config


class McrTeardownConfig(Config):
    def __init__(
        self,
        args: McrTeardownArgs,
        profile: Optional[str] = None,
        strict: bool = False,
        allow_multiple_only_for_testing: bool = False,
    ) -> None:
        self._args = args
        super().__init__(
            args,
            profile=profile,
            strict=strict,
            allow_multiple_only_for_testing=allow_multiple_only_for_testing,
        )

    def reload(self) -> None:
        super().reload()
        self.live_event_url = self.live_event_url_template.fill(
            {"BOXCAST_EVENT_ID": self._args.boxcast_event_id}
        )
        self.vimeo_video_title = self.vimeo_video_title_template.fill(
            {
                "MESSAGE_SERIES": self._args.message_series,
                "MESSAGE_TITLE": self._args.message_title,
            }
        )

    def fill_placeholders(self, text: str) -> str:
        text = text.replace("%{boxcast.live_event_url}%", self.live_event_url)
        text = text.replace("%{vimeo.video_title}%", self.vimeo_video_title)
        return super().fill_placeholders(text)
