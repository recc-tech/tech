from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Set

from common import ReccConfig


class McrSetupConfig(ReccConfig):
    def __init__(
        self,
        home_dir: Path,
        ui: Literal["console", "tk"],
        verbose: bool,
        no_run: bool,
        auto_tasks: Optional[Set[str]],
        show_browser: bool,
        now: datetime,
    ):
        super().__init__(
            home_dir=home_dir,
            now=now or datetime.now(),
            ui=ui,
            verbose=verbose,
            no_run=no_run,
            auto_tasks=auto_tasks,
        )
        self.show_browser = show_browser

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
    def backup_slides_json_file(self) -> Path:
        return self.assets_by_service_dir.joinpath("slides.json")

    @property
    def vmix_preset_file(self) -> Path:
        return self.home_dir.joinpath(
            "vMix Presets", f"{self.now.strftime('%Y-%m-%d')} Live.vmix"
        )

    @property
    def log_file(self) -> Path:
        return self.log_dir.joinpath(
            f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')} mcr_setup.log"
        )

    @property
    def webdriver_log_file(self) -> Path:
        return self.log_dir.joinpath(
            f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')} mcr_setup_webdriver.log"
        )

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
