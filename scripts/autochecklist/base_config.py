from __future__ import annotations

from typing import Literal


class BaseConfig:
    """
    Central location for shared information like video titles, file paths, etc.
    """

    def __init__(
        self,
        ui: Literal["console", "tk"] = "tk",
        verbose: bool = False,
        no_run: bool = False,
    ) -> None:
        self.ui: Literal["console", "tk"] = ui
        self.verbose = verbose
        self.no_run = no_run
        # TODO: Support list of tasks to automate

    def fill_placeholders(self, text: str) -> str:
        if "%{" in text or "}%" in text:
            raise ValueError(f'Text "{text}" contains an unknown placeholder.')

        return text
