from __future__ import annotations

import sys
from pathlib import Path

import autochecklist
import lib.mcr_teardown as mcr_teardown
from config import McrTeardownArgs, McrTeardownConfig
from lib import ReccDependencyProvider

if __name__ == "__main__":
    args = McrTeardownArgs.parse(sys.argv)
    config = McrTeardownConfig(args)
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.mcr_teardown_log,
        script_name="MCR Teardown",
        description=McrTeardownArgs.DESCRIPTION,
        show_statuses_by_default=False,
    )
    tasks = Path(__file__).parent.joinpath("config").joinpath("mcr_teardown_tasks.json")
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dependency_provider,
        tasks=tasks,
        module=mcr_teardown,
    )
