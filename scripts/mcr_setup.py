import typing
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import mcr_setup.tasks
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Script,
    TkMessenger,
)
from external_services import (
    CredentialStore,
    PlanningCenterClient,
    ReccWebDriver,
    VmixClient,
)
from lib import parse_directory
from lib.slides import BibleVerseFinder, SlideBlueprintReader, SlideGenerator
from mcr_setup.config import McrSetupConfig

_DESCRIPTION = "This script will guide you through the steps to setting up the MCR visuals station for a Sunday gathering."


class McrSetupScript(Script[McrSetupConfig]):
    def __init__(self) -> None:
        self._web_driver: Optional[ReccWebDriver] = None

    def create_config(self) -> McrSetupConfig:
        parser = ArgumentParser(description=_DESCRIPTION)

        advanced_args = parser.add_argument_group("Advanced arguments")
        advanced_args.add_argument(
            "--home-dir",
            type=parse_directory,
            default="D:\\Users\\Tech\\Documents",
            help="The home directory.",
        )
        advanced_args.add_argument(
            "--ui",
            choices=["console", "tk"],
            default="tk",
            help="User interface to use.",
        )

        debug_args = parser.add_argument_group("Debug arguments")
        debug_args.add_argument(
            "--verbose",
            action="store_true",
            help="This flag is only applicable when the console UI is used. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
        )
        debug_args.add_argument(
            "--no-run",
            action="store_true",
            help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
        )
        debug_args.add_argument(
            "--auto",
            action="append",
            default=None,
            help="Specify which tasks to automate. You can also provide 'none' to automate none of the tasks. By default, all tasks that can be automated are automated.",
        )
        debug_args.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )
        debug_args.add_argument(
            "--date",
            type=lambda x: datetime.strptime(x, "%Y-%m-%d").date(),
            help="Pretend the script is running on a different date.",
        )

        args = parser.parse_args()
        if args.auto is not None:
            if "none" in args.auto and len(args.auto) > 1:
                parser.error(
                    "If 'none' is included in --auto, it must be the only value."
                )
            if args.auto == ["none"]:
                args.auto = typing.cast(List[str], [])

        return McrSetupConfig(
            home_dir=args.home_dir,
            ui=args.ui,
            verbose=args.verbose,
            no_run=args.no_run,
            auto_tasks=set(args.auto) if args.auto is not None else None,
            show_browser=args.show_browser,
            now=(
                datetime.combine(args.date, datetime.now().time())
                if args.date
                else datetime.now()
            ),
        )

    def create_messenger(self, config: McrSetupConfig) -> Messenger:
        file_messenger = FileMessenger(log_file=config.log_file)
        input_messenger = (
            ConsoleMessenger(
                description=f"{_DESCRIPTION}\n\nIf you need to stop the script, press CTRL+C or close the terminal window.",
                show_task_status=config.verbose,
            )
            if config.ui == "console"
            else TkMessenger(
                title="MCR Setup",
                description=_DESCRIPTION,
            )
        )
        messenger = Messenger(
            file_messenger=file_messenger, input_messenger=input_messenger
        )
        return messenger

    def create_services(
        self, config: McrSetupConfig, messenger: Messenger
    ) -> Tuple[Path, FunctionFinder]:
        credential_store = CredentialStore(messenger)
        planning_center_client = PlanningCenterClient(messenger, credential_store)
        vmix_client = VmixClient()
        web_driver = ReccWebDriver(
            messenger=messenger,
            headless=not config.show_browser,
            log_file=config.webdriver_log_file,
        )
        bible_verse_finder = BibleVerseFinder(
            web_driver,
            messenger,
            cancellation_token=None,
        )
        reader = SlideBlueprintReader(messenger, bible_verse_finder)
        generator = SlideGenerator(messenger)
        function_finder = FunctionFinder(
            mcr_setup.tasks,
            [
                planning_center_client,
                vmix_client,
                config,
                messenger,
                reader,
                generator,
            ],
            messenger,
        )
        task_list_file = (
            Path(__file__).parent.joinpath("mcr_setup").joinpath("tasks.json")
        )
        return task_list_file, function_finder

    def shut_down(self, config: McrSetupConfig) -> None:
        if self._web_driver is not None:
            self._web_driver.quit()


if __name__ == "__main__":
    McrSetupScript().run()
