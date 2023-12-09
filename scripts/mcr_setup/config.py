from datetime import datetime
from pathlib import Path
from typing import Optional

from common import ReccConfig


class McrSetupConfig(ReccConfig):
    def __init__(self, home_dir: Path, now: Optional[datetime] = None):
        super().__init__(home_dir, now or datetime.now())

    @property
    def assets_by_service_dir(self) -> Path:
        return self.home_dir.joinpath(
            "vMix Assets", "By Service", self.now.strftime("%Y-%m-%d")
        )

    @property
    def assets_by_type_dir(self) -> Path:
        return self.home_dir.joinpath("vMix Assets", "By Type")

    @property
    def assets_by_type_images_dir(self) -> Path:
        return self.assets_by_type_dir.joinpath("Images")

    @property
    def assets_by_type_videos_dir(self) -> Path:
        return self.assets_by_type_dir.joinpath("Videos")

    @property
    def assets_by_type_archive_dir(self) -> Path:
        return self.assets_by_type_dir.joinpath("Archive")

    @property
    def message_notes_file(self) -> Path:
        return self.assets_by_service_dir.joinpath("message-notes.txt")

    @property
    def vmix_preset_file(self) -> Path:
        return self.home_dir.joinpath(
            "vMix Presets", f"{self.now.strftime('%Y-%m-%d')} Live.vmix"
        )

    @property
    def log_file(self) -> Path:
        return self.log_dir.joinpath(
            f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')} mcr_setup.log"
        ).resolve()

    def fill_placeholders(self, text: str) -> str:
        text = (
            text.replace(
                "%{ASSETS_BY_SERVICE_DIR}%", self.assets_by_service_dir.as_posix()
            )
            .replace("%{ASSETS_BY_TYPE_DIR}%", self.assets_by_type_dir.as_posix())
            .replace("%{MESSAGE_NOTES_FILE}%", self.message_notes_file.as_posix())
            .replace(
                "%{ASSETS_BY_TYPE_ARCHIVE_DIR}%",
                self.assets_by_type_archive_dir.as_posix(),
            )
            .replace("%{VMIX_PRESET_FILE}%", self.vmix_preset_file.as_posix())
        )

        # Call the superclass' method *after* the subclass' method so that the check for unknown placeholders happens
        # at the end
        return super().fill_placeholders(text)
