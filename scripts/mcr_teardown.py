from __future__ import annotations

import sys
from pathlib import Path

import autochecklist
import lib.mcr_teardown as mcr_teardown
from config import McrTeardownArgs, McrTeardownConfig
from lib import ReccDependencyProvider, SimplifiedMessengerSettings


def main(
    args: McrTeardownArgs, config: McrTeardownConfig, dep: ReccDependencyProvider
) -> None:
    tasks = Path(__file__).parent.joinpath("config").joinpath("mcr_teardown_tasks.json")
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=tasks,
        module=mcr_teardown,
    )


if __name__ == "__main__":
    args = McrTeardownArgs.parse(sys.argv)
    config = McrTeardownConfig(args)
    msg = SimplifiedMessengerSettings(
        log_file=config.mcr_teardown_log,
        script_name="MCR Teardown",
        description=McrTeardownArgs.DESCRIPTION,
        show_statuses_by_default=False,
    )
    dependency_provider = ReccDependencyProvider(
        args=args, config=config, messenger=msg
    )
    main(args, config, dependency_provider)
