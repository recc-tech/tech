from pathlib import Path
from typing import Optional

from args import ReccArgs

from .config import Config


class McrSetupConfig(Config):
    def __init__(
        self,
        args: ReccArgs,
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

    @property
    def message_notes_file(self) -> Path:
        return self.assets_by_service_dir.joinpath(self.message_notes_filename)

    @property
    def slide_blueprints_file(self) -> Path:
        return self.assets_by_service_dir.joinpath(self.blueprints_filename)

    def fill_placeholders(self, text: str) -> str:
        text = text.replace(
            "%{slides.message_notes}%", self.message_notes_file.as_posix()
        )
        text = text.replace(
            "%{slides.blueprints}%", self.slide_blueprints_file.as_posix()
        )
        return super().fill_placeholders(text)
