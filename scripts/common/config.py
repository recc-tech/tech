from datetime import datetime
from pathlib import Path

from autochecklist import BaseConfig


class ReccConfig(BaseConfig):
    def __init__(self, home_dir: Path, now: datetime) -> None:
        super().__init__()
        self._home_dir = home_dir.resolve()
        self._now = now

    @property
    def home_dir(self) -> Path:
        return self._home_dir

    @property
    def log_dir(self) -> Path:
        return self.home_dir.joinpath("Logs")

    @property
    def now(self) -> datetime:
        return self._now
