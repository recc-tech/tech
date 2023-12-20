from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import mcr_setup.tasks
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Script,
    TkMessenger,
)
from common import CredentialStore, PlanningCenterClient, ReccWebDriver, parse_directory
from mcr_setup.config import McrSetupConfig
from slides import BibleVerseFinder, SlideBlueprintReader, SlideGenerator

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
        # TODO
        # debug_args.add_argument(
        #     "--no-auto",
        #     action="store_true",
        #     help="If this flag is provided, no tasks will be completed automatically - user input will be required for each one.",
        # )
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
        if args.verbose and not args.text_ui:
            parser.error(
                "The --verbose flag is only applicable when the --text-ui flag is also provided."
            )

        return McrSetupConfig(
            home_dir=args.home_dir,
            ui=args.ui,
            verbose=args.verbose,
            no_run=args.no_run,
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
            # TODO
            # None if args.no_auto else mcr_setup.tasks,
            mcr_setup.tasks,
            [
                planning_center_client,
                config,
                credential_store,
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
