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
            create_dirs=False,
        )

    def reload(self, create_dirs: bool = False) -> None:
        super().reload(create_dirs=create_dirs)
        self.vimeo_video_title = self.vimeo_video_title_template.fill(
            {
                "MESSAGE_SERIES": self._args.message_series,
                "MESSAGE_TITLE": self._args.message_title,
            }
        )

    def fill_placeholders(self, text: str) -> str:
        text = text.replace("%{vimeo.video_title}%", self.vimeo_video_title)
        return super().fill_placeholders(text)
