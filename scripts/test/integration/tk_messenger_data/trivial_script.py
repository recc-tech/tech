from __future__ import annotations

import sys
from pathlib import Path

import autochecklist
from args import ReccArgs
from autochecklist import (
    BaseArgs,
    BaseConfig,
    DependencyProvider,
    MessengerSettings,
    TaskModel,
)

_TEMP_DIR = Path(__file__).parent.parent.joinpath("tk_messenger_temp")


def main(args: BaseArgs, config: BaseConfig, dep: DependencyProvider) -> None:
    tasks = TaskModel(
        name="foo",
        description="Do nothing.",
        prerequisites=set(),
        subtasks=[],
        only_auto=False,
        func=lambda: None,
    )
    autochecklist.run(
        args=args, config=config, dependency_provider=dep, tasks=tasks, module=None
    )


if __name__ == "__main__":
    args = ReccArgs.parse(sys.argv)
    config = BaseConfig()
    msg = MessengerSettings(
        log_file=_TEMP_DIR.joinpath("trivial_script.log"),
        script_name="TkMessenger Test",
        description="A trivial script for testing the TkMessenger.",
        show_statuses_by_default=True,
        ui_theme="dark",
        icon=None,
        auto_close=args.auto_close,
    )
    dependency_provider = DependencyProvider(args=args, config=config, messenger=msg)
    main(args, config, dependency_provider)
