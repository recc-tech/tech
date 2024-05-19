import sys
from pathlib import Path

import autochecklist
import lib.mcr_setup as mcr_setup
from args import McrSetupArgs
from config import McrSetupConfig
from lib import ReccDependencyProvider

if __name__ == "__main__":
    # TODO: Write a main function which takes these as arguments so that the
    # startup can be tested?
    args = McrSetupArgs.parse(sys.argv)
    config = McrSetupConfig(args, profile=None, strict=False)
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.mcr_setup_log,
        script_name="MCR Setup",
        description=McrSetupArgs.DESCRIPTION,
        show_statuses_by_default=False,
        headless=not args.show_browser,
        webdriver_log=config.mcr_setup_webdriver_log,
    )
    autochecklist.run(
        args=args,
        config=config,
        tasks=Path(__file__).parent.joinpath("config").joinpath("mcr_setup_tasks.json"),
        module=mcr_setup,
        dependency_provider=dependency_provider,
    )
