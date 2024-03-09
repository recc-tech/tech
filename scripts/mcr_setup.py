import sys
from pathlib import Path
from typing import Optional, Tuple

import lib.mcr_setup as mcr_setup
from args import McrSetupArgs
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Script,
    TkMessenger,
)
from config import Config, McrSetupConfig
from external_services import (
    CredentialStore,
    PlanningCenterClient,
    ReccWebDriver,
    VmixClient,
)
from lib import AssetManager, BibleVerseFinder, SlideBlueprintReader, SlideGenerator


class McrSetupScript(Script[McrSetupArgs, McrSetupConfig]):
    def __init__(self) -> None:
        self._web_driver: Optional[ReccWebDriver] = None

    def parse_args(self) -> McrSetupArgs:
        return McrSetupArgs.parse(sys.argv)

    def create_config(self, args: McrSetupArgs) -> McrSetupConfig:
        return McrSetupConfig(args, profile=None, strict=False)

    def create_messenger(self, args: McrSetupArgs, config: Config) -> Messenger:
        file_messenger = FileMessenger(log_file=config.mcr_setup_log)
        input_messenger = (
            ConsoleMessenger(
                description=f"{McrSetupArgs.DESCRIPTION}\n\nIf you need to stop the script, press CTRL+C or close the terminal window.",
                show_task_status=args.verbose,
            )
            if args.ui == "console"
            else TkMessenger(
                title="MCR Setup",
                description=McrSetupArgs.DESCRIPTION,
                theme=config.ui_theme,
                show_statuses_by_default=False,
            )
        )
        messenger = Messenger(
            file_messenger=file_messenger, input_messenger=input_messenger
        )
        return messenger

    def create_services(
        self, args: McrSetupArgs, config: Config, messenger: Messenger
    ) -> Tuple[Path, FunctionFinder]:
        credential_store = CredentialStore(messenger)
        planning_center_client = PlanningCenterClient(
            messenger, credential_store, config
        )
        vmix_client = VmixClient(config=config)
        web_driver = ReccWebDriver(
            messenger=messenger,
            headless=not args.show_browser,
            log_file=config.mcr_setup_webdriver_log,
        )
        bible_verse_finder = BibleVerseFinder(
            web_driver,
            messenger,
            cancellation_token=None,
        )
        reader = SlideBlueprintReader(messenger, bible_verse_finder)
        generator = SlideGenerator(messenger, config)
        manager = AssetManager(config)
        function_finder = FunctionFinder(
            mcr_setup,
            [
                planning_center_client,
                vmix_client,
                config,
                messenger,
                reader,
                generator,
                manager,
            ],
            messenger,
        )
        task_list_file = (
            Path(__file__).parent.joinpath("config").joinpath("mcr_setup_tasks.json")
        )
        return task_list_file, function_finder

    def shut_down(self, args: McrSetupArgs, config: Config) -> None:
        if self._web_driver is not None:
            self._web_driver.quit()


if __name__ == "__main__":
    McrSetupScript().run()
