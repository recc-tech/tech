import typing
from pathlib import Path
from typing import Optional, Type, TypeVar

from args import ReccArgs
from autochecklist import DependencyProvider, Messenger
from config import Config
from external_services import (
    CredentialStore,
    InputPolicy,
    PlanningCenterClient,
    ReccVimeoClient,
    VmixClient,
)
from external_services.bible import BibleVerseFinder
from external_services.boxcast import BoxCastApiClient

from .assets import AssetManager
from .slides import SlideBlueprintReader, SlideGenerator

T = TypeVar("T")


class ReccDependencyProvider(DependencyProvider):
    def __init__(
        self,
        *,
        args: ReccArgs,
        config: Config,
        log_file: Path,
        script_name: str,
        description: str,
        show_statuses_by_default: bool,
        messenger: Optional[Messenger] = None,
        lazy_login: bool = False,
        credentials_input_policy: Optional[InputPolicy] = None,
        confirm_exit_message: str = "Are you sure you want to exit? The script is not done yet.",
    ) -> None:
        super().__init__(
            args=args,
            config=config,
            messenger=messenger,
            log_file=log_file,
            script_name=script_name,
            description=description,
            confirm_exit_message=confirm_exit_message,
            show_statuses_by_default=show_statuses_by_default,
            ui_theme=config.ui_theme,
            icon=Path(__file__).parent.parent.parent.joinpath("icon_512x512.png"),
            auto_close_messenger=args.auto_close,
        )

        # Optional args
        self._lazy_login = lazy_login
        self._credentials_input_policy = credentials_input_policy

        # Services
        self._config = config
        self._credential_store: Optional[CredentialStore] = None
        self._planning_center_client: Optional[PlanningCenterClient] = None
        self._vmix_client: Optional[VmixClient] = None
        self._bible_verse_finder: Optional[BibleVerseFinder] = None
        self._slide_blueprint_reader: Optional[SlideBlueprintReader] = None
        self._slide_generator: Optional[SlideGenerator] = None
        self._asset_manager: Optional[AssetManager] = None
        self._vimeo_client: Optional[ReccVimeoClient] = None
        self._boxcast_client: Optional[BoxCastApiClient] = None

    def get(self, typ: Type[T]) -> T:
        method_by_type = {
            type(self._args): lambda: self._args,
            type(self._config): lambda: self._config,
            type(self.messenger): lambda: self.messenger,
            CredentialStore: self._get_credential_store,
            PlanningCenterClient: self._get_planning_center_client,
            VmixClient: self._get_vmix_client,
            BibleVerseFinder: self._get_bible_verse_finder,
            SlideBlueprintReader: self._get_slide_blueprint_reader,
            SlideGenerator: self._get_slide_generator,
            AssetManager: self._get_asset_manager,
            ReccVimeoClient: self._get_vimeo_client,
            BoxCastApiClient: self._get_boxcast_client,
        }
        for t, f in method_by_type.items():
            if issubclass(t, typ):
                return typing.cast(T, f())
        raise ValueError(f"Unknown argument type {typ.__name__}")

    def _get_credential_store(self) -> CredentialStore:
        if self._credential_store is None:
            self._credential_store = CredentialStore(
                messenger=self.messenger,
                request_input=self._credentials_input_policy,
            )
        return self._credential_store

    def _get_planning_center_client(self) -> PlanningCenterClient:
        if self._planning_center_client is None:
            self._planning_center_client = PlanningCenterClient(
                config=self._config,
                messenger=self.messenger,
                credential_store=self._get_credential_store(),
                lazy_login=self._lazy_login,
            )
        return self._planning_center_client

    def _get_vmix_client(self) -> VmixClient:
        if self._vmix_client is None:
            self._vmix_client = VmixClient(config=self._config)
        return self._vmix_client

    def _get_bible_verse_finder(self) -> BibleVerseFinder:
        if self._bible_verse_finder is None:
            self._bible_verse_finder = BibleVerseFinder()
        return self._bible_verse_finder

    def _get_slide_blueprint_reader(self) -> SlideBlueprintReader:
        if self._slide_blueprint_reader is None:
            self._slide_blueprint_reader = SlideBlueprintReader(
                messenger=self.messenger,
                bible_verse_finder=self._get_bible_verse_finder(),
            )
        return self._slide_blueprint_reader

    def _get_slide_generator(self) -> SlideGenerator:
        if self._slide_generator is None:
            self._slide_generator = SlideGenerator(
                config=self._config,
                messenger=self.messenger,
            )
        return self._slide_generator

    def _get_asset_manager(self) -> AssetManager:
        if self._asset_manager is None:
            self._asset_manager = AssetManager(config=self._config)
        return self._asset_manager

    def _get_vimeo_client(self) -> ReccVimeoClient:
        if self._vimeo_client is None:
            self._vimeo_client = ReccVimeoClient(
                messenger=self.messenger,
                credential_store=self._get_credential_store(),
                config=self._config,
                cancellation_token=None,
                lazy_login=self._lazy_login,
            )
        return self._vimeo_client

    def _get_boxcast_client(self) -> BoxCastApiClient:
        if self._boxcast_client is None:
            self._boxcast_client = BoxCastApiClient(
                messenger=self.messenger,
                credential_store=self._get_credential_store(),
                config=self._config,
                lazy_login=self._lazy_login,
            )
        return self._boxcast_client
