from __future__ import annotations

from typing import Literal, Optional, Set


class BaseConfig:
    """
    Central location for shared information like video titles, file paths, etc.
    """

    def __init__(
        self,
        ui: Literal["console", "tk"],
        verbose: bool,
        no_run: bool,
        auto_tasks: Optional[Set[str]],
    ) -> None:
        self.ui: Literal["console", "tk"] = ui
        self.verbose = verbose
        self.no_run = no_run
        self.auto_tasks = auto_tasks
        """
        Whitelist of tasks that can be automated. `None` means all tasks that
        can be automated should be automated.
        """

    def fill_placeholders(self, text: str) -> str:
        if "%{" in text or "}%" in text:
            raise ValueError(f'Text "{text}" contains an unknown placeholder.')

        return text
