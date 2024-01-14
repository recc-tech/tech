import platform
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Literal, Tuple, Union

import lib
from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Script,
    TaskModel,
    TkMessenger,
)
from lib import CredentialStore, PlanningCenterClient, ReccConfig

_DESCRIPTION = (
    "This script will download the assets from today's plan in Planning Center Online."
)


class DownloadAssetsConfig(ReccConfig):
    def __init__(
        self,
        home_dir: Path,
        ui: Literal["console", "tk"],
        verbose: bool,
        station: Literal["foh", "mcr"],
    ) -> None:
        super().__init__(
            home_dir=home_dir,
            now=datetime.now(),
            ui=ui,
            verbose=verbose,
            no_run=False,
            auto_tasks=None,
        )
        self.station = station

    @property
    def assets_by_service_dir(self) -> Path:
        if self.station == "mcr":
            return self.home_dir.joinpath(
                "vMix Assets", "By Service", self.now.strftime("%Y-%m-%d")
            )
        else:
            return self.assets_by_type_dir

    @property
    def assets_by_type_dir(self) -> Path:
        if self.station == "mcr":
            return self.home_dir.joinpath("vMix Assets", "By Type")
        else:
            return self.home_dir.joinpath("ProPresenter Assets")

    @property
    def assets_by_type_images_dir(self) -> Path:
        if self.station == "mcr":
            return self.assets_by_type_dir.joinpath("Images")
        else:
            return self.assets_by_type_dir

    @property
    def assets_by_type_videos_dir(self) -> Path:
        if self.station == "mcr":
            return self.assets_by_type_dir.joinpath("Videos")
        else:
            return self.assets_by_type_dir

    @property
    def temp_assets_dir(self) -> Path:
        return self.assets_by_type_dir.joinpath("Temp")

    @property
    def log_file(self) -> Path:
        return self.log_dir.joinpath(
            f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')} download_pco_assets.log"
        )

    @property
    def download_kids_video(self) -> bool:
        return self.station == "mcr"

    @property
    def download_notes_docx(self) -> bool:
        return self.station == "mcr"


class DownloadAssetsScript(Script[DownloadAssetsConfig]):
    def create_config(self) -> DownloadAssetsConfig:
        parser = ArgumentParser(description=_DESCRIPTION)

        parser.add_argument(
            "--station",
            choices=["foh", "mcr"],
            default="foh" if platform.system() == "Darwin" else "mcr",
            help="Which station this script is running on. This determines the expected directory structure.",
        )

        advanced_args = parser.add_argument_group("Advanced arguments")
        advanced_args.add_argument(
            "--home-dir",
            type=lib.parse_directory,
            default="D:\\Users\\Tech\\Documents",
            help="The home directory.",
        )
        advanced_args.add_argument(
            "--ui",
            choices=["console", "tk"],
            default="tk",
            help="User interface to use.",
        )
        advanced_args.add_argument(
            "--verbose",
            action="store_true",
            help="This flag is only applicable when the flag --text-ui is also provided. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
        )

        args = parser.parse_args()

        return DownloadAssetsConfig(
            home_dir=args.home_dir,
            ui=args.ui,
            verbose=args.verbose,
            station=args.station,
        )

    def create_messenger(self, config: DownloadAssetsConfig) -> Messenger:
        file_messenger = FileMessenger(config.log_file)
        input_messenger = (
            TkMessenger("Autochecklist", _DESCRIPTION)
            if config.ui == "tk"
            else ConsoleMessenger(_DESCRIPTION, show_task_status=config.verbose)
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, config: DownloadAssetsConfig, messenger: Messenger
    ) -> Tuple[Union[Path, TaskModel], FunctionFinder]:
        credential_store = CredentialStore(messenger)
        planning_center_client = PlanningCenterClient(messenger, credential_store)
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[messenger, config, planning_center_client],
            messenger=messenger,
        )
        task_model = TaskModel(
            name="download_pco_assets",
            description="Failed to download assets.",
            only_auto=True,
        )
        return task_model, function_finder


def download_pco_assets(
    client: PlanningCenterClient,
    messenger: Messenger,
    config: DownloadAssetsConfig,
):
    lib.download_pco_assets(
        client=client,
        messenger=messenger,
        today=config.now,
        assets_by_service_dir=config.assets_by_service_dir,
        temp_assets_dir=config.temp_assets_dir,
        assets_by_type_videos_dir=config.assets_by_type_videos_dir,
        assets_by_type_images_dir=config.assets_by_type_images_dir,
        download_kids_video=config.download_kids_video,
        download_notes_docx=config.download_notes_docx,
    )


if __name__ == "__main__":
    DownloadAssetsScript().run()
