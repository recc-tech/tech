from pathlib import Path

from args import McrSetupArgs

from .config import Config


class McrSetupConfig(Config):
    def __init__(self, args: McrSetupArgs, strict: bool = False) -> None:
        self._args = args
        super().__init__(args, strict)

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
