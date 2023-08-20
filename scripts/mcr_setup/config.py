from datetime import datetime
from pathlib import Path

from autochecklist import BaseConfig


class McrSetupConfig(BaseConfig):
    def __init__(self, home_dir: Path):
        self._home_dir = home_dir.resolve()

        now = datetime.now()
        self._start_date_ymd = now.strftime("%Y-%m-%d")
        self._start_time = now.strftime("%H-%M-%S")

    @property
    def assets_by_service_dir(self) -> Path:
        return (
            self._home_dir.joinpath("vMix Assets")
            .joinpath("By Service")
            .joinpath(self._start_date_ymd)
        )

    @property
    def assets_by_type_dir(self) -> Path:
        return self._home_dir.joinpath("vMix Assets").joinpath("By Type")

    @property
    def assets_by_type_archive_dir(self) -> Path:
        return self.assets_by_type_dir.joinpath("Archive")

    @property
    def message_notes_file(self) -> Path:
        return self.assets_by_service_dir.joinpath("message-notes.txt")

    @property
    def vmix_preset_file(self) -> Path:
        return self._home_dir.joinpath("vMix Presets").joinpath(
            f"{self._start_date_ymd} Live.vmix"
        )

    # TODO: Move this to an ReccConfig class in the common package?
    @property
    def log_dir(self) -> Path:
        return self._home_dir.joinpath("Logs")

    @property
    def log_file(self) -> Path:
        return self.log_dir.joinpath(
            f"{self._start_date_ymd} {self._start_time} mcr_setup.log"
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
