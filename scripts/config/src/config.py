from __future__ import annotations

import os
import platform
import typing
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Dict, List, Literal, Optional, Set, Tuple, Type, TypeVar

import tomli
from args import ReccArgs, parse_directory, parse_file
from autochecklist import BaseArgs, BaseConfig

ImgMode = Literal["1", "L", "RGB", "RGBA"]
HorizAlign = Literal["left", "center", "right"]
_HORIZ_ALIGNS: Set[HorizAlign] = {"left", "center", "right"}
VertAlign = Literal["top", "center", "bottom"]
_VERT_ALIGNS: Set[VertAlign] = {"top", "center", "bottom"}
FontStyle = Literal["normal", "italic", "oblique"]
_STYLES: Set[FontStyle] = {"normal", "italic", "oblique"}
T = TypeVar("T")


@dataclass(frozen=True)
class Bbox:
    """Bounding box."""

    left: int
    top: int
    right: int
    bottom: int

    @staticmethod
    def xywh(x: int, y: int, w: int, h: int) -> Bbox:
        return Bbox(left=x, top=y, right=x + w, bottom=y + h)

    def get_horizontal_centre(self) -> float:
        return self.left + (self.right - self.left) / 2

    def get_vertical_centre(self) -> float:
        return self.top + (self.bottom - self.top) / 2

    def get_width(self) -> int:
        return self.right - self.left

    def get_height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class Font:
    family: List[str]
    style: FontStyle
    max_size: int
    min_size: int


@dataclass(frozen=True)
class Textbox:
    bbox: Bbox
    font: Font
    horiz_align: HorizAlign
    vert_align: VertAlign
    text_colour: str
    bold: bool
    line_spacing: float

    @property
    def stroke_width(self) -> int:
        return 1 if self.bold else 0


@dataclass(frozen=True)
class Rectangle:
    bbox: Bbox
    background_colour: str


@dataclass(frozen=True)
class NoFooterSlideStyle:
    width: int
    height: int
    background_colour: str
    body: Textbox
    shapes: List[Rectangle]

    @property
    def mode(self) -> ImgMode:
        # TODO: Determine this automatically in each case based on background
        # and font colours.
        # Go with minimum value: e.g., 1 for only b/w, L for greyscale, etc.
        return "RGBA"

    @property
    def width_height(self) -> Tuple[int, int]:
        return (self.width, self.height)


@dataclass(frozen=True)
class FooterSlideStyle:
    width: int
    height: int
    background_colour: str
    body: Textbox
    footer: Textbox
    shapes: List[Rectangle]

    @property
    def mode(self) -> ImgMode:
        return "RGBA"

    @property
    def width_height(self) -> Tuple[int, int]:
        return (self.width, self.height)


_CONFIG_DIR = Path(__file__).resolve().parent.parent
_PROFILE_SELECT_FILE = _CONFIG_DIR.joinpath("active_profile.txt").resolve()
_PROFILES_DIR = _CONFIG_DIR.joinpath("profiles")


def locate_profile(profile: str) -> Path:
    return _PROFILES_DIR.joinpath(f"{profile}.toml").resolve()


def get_active_profile() -> Optional[str]:
    try:
        return _PROFILE_SELECT_FILE.read_text().strip()
    except FileNotFoundError:
        return None


def activate_profile(profile: str) -> None:
    f = locate_profile(profile)
    if not f.is_file():
        raise ValueError(
            f"There is no profile called '{profile}' (expected to find it at {f.as_posix()})."
        )
    try:
        _PROFILE_SELECT_FILE.write_text(f"{profile}\n")
    except Exception as e:
        raise ValueError(
            f"{_PROFILE_SELECT_FILE.as_posix()} is missing and could not be created."
        ) from e


def list_profiles() -> Set[str]:
    files = os.listdir(_PROFILES_DIR)
    return {f[:-5] for f in files if f.endswith(".toml")}


@dataclass
class StringTemplate:
    template: str

    def fill(self, values: Dict[str, str]) -> str:
        t = self.template
        for k, v in values.items():
            placeholder = "!{" + k + "}!"
            t = t.replace(placeholder, v)
        if "!{" in t or "}!" in t:
            raise ValueError(f"Unfilled placeholder in '{t}'.")
        return t


# TODO: Test placeholder filling (valid cases, circular references, etc.)
class ConfigFileReader(AbstractContextManager[object]):
    def __init__(self, args: BaseArgs, profile: str, strict: bool) -> None:
        self._args = args
        self._strict = strict
        self._is_read_by_key: Dict[str, bool] = {}
        self._data = self._read_global_config()
        # IMPORTANT: read the local file second so that it overrides values
        # found in the global file
        self._data |= self._read_local_config(profile)
        self._data = self._resolve(self._data)

    def _read_global_config(self) -> Dict[str, object]:
        global_file = _CONFIG_DIR.joinpath("config.toml").resolve()
        try:
            with open(global_file, "rb") as f:
                return self._flatten(tomli.load(f))
        except FileNotFoundError as e:
            raise ValueError(
                f"Failed to read global config because {global_file.as_posix()} is missing."
            ) from e
        except Exception as e:
            raise ValueError(
                "Failed to read global config due to an unknown error."
            ) from e

    def _read_local_config(self, profile: str) -> Dict[str, object]:
        local_file = locate_profile(profile)
        try:
            with open(local_file, "rb") as f:
                return self._flatten(tomli.load(f))
        except FileNotFoundError as e:
            raise ValueError(
                f"There is no profile called '{profile}' (expected to find it at {local_file.as_posix()})."
            ) from e
        except Exception as e:
            raise ValueError(
                "Failed to read local config due to an unknown error."
            ) from e

    def _flatten(self, data: Dict[str, object]) -> Dict[str, object]:
        out_data: Dict[str, object] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                value = self._flatten(typing.cast(Dict[str, object], value))
                out_data |= {f"{key}.{k}": v for (k, v) in value.items()}
            else:
                out_data[key] = value
        return out_data

    def _resolve(self, raw_data: Dict[str, object]) -> Dict[str, object]:
        data: Dict[str, object] = {}
        for k, v in raw_data.items():
            if isinstance(v, str):
                try:
                    data[k] = self.fill_placeholders(v)
                except Exception as e:
                    raise ValueError(
                        f"Failed to fill placeholders in configuration value {k}."
                    ) from e
            else:
                data[k] = v
        return data

    def __enter__(self) -> ConfigFileReader:
        self._is_read_by_key = {key: False for key in self._data.keys()}
        return self

    def __exit__(
        self,
        __exc_type: Optional[Type[BaseException]],
        __exc_value: Optional[BaseException],
        __traceback: Optional[TracebackType],
    ) -> bool | None:
        if __exc_type is not None or __exc_value is not None or __traceback is not None:
            return
        if not self._strict:
            return
        unused_keys = {k for (k, v) in self._is_read_by_key.items() if not v}
        if len(unused_keys) > 0:
            raise ValueError(
                f"The following configuration values are unrecognized: {unused_keys}"
            )

    def fill_placeholders(self, value: str) -> str:
        return self._fill_placeholders(value, [])

    def _fill_placeholders(self, template: str, history: List[str]) -> str:
        while True:
            start = template.find("%{")
            end = template.find("}%")
            if start < 0 and end < 0:
                return template
            elif start < 0:
                raise ValueError(f"Mismatched %{{ in '{template}'.")
            elif end < 0 or end < start:
                raise ValueError(f"Mismatched }}% in '{template}'.")
            else:
                placeholder_key = template[start + 2 : end]
                placeholder = "%{" + placeholder_key + "}%"
                placeholder_value = self._get_and_fill(placeholder_key, history)
                template = template.replace(placeholder, str(placeholder_value))

    def _get_and_fill(self, key: str, history: List[str]) -> str:
        value = self._args.get(key)
        if value is None:
            raw_value = self._data.get(key, None)
            if raw_value is None:
                raise ValueError(f"Missing configuration value {key}.")
            if isinstance(raw_value, str):
                value = self._fill_placeholders(raw_value, history + [key])
        return str(value)

    def get(self, key: str) -> object:
        """Look up the given key and raise an exception if not found."""
        self._is_read_by_key[key] = True
        value = self._data.get(key, None)
        if value is None:
            raise ValueError(f"Missing configuration value {key}.")
        else:
            return value

    def _get_typed(self, key: str, cls: Type[T], clsname: str) -> T:
        value = self.get(key)
        if not isinstance(value, cls):
            raise ValueError(
                f"Expected configuration value {key} to be {clsname}, but found type {type(value)}."
            )
        return value

    def get_str(self, key: str) -> str:
        return self._get_typed(key, str, "a string")

    def get_int(self, key: str) -> int:
        return self._get_typed(key, int, "a whole number")

    def get_positive_int(self, key: str) -> int:
        x = self.get_int(key)
        if x <= 0:
            raise ValueError(
                f"Expected configuration value {key} to be positive, but found value {x}"
            )
        return x

    def get_nonneg_int(self, key: str) -> int:
        x = self.get_int(key)
        if x < 0:
            raise ValueError(
                f"Expected configuration value {key} to be non-negative, but found value {x}."
            )
        return x

    def get_bool(self, key: str) -> bool:
        return self._get_typed(key, bool, "true or false")

    def get_enum(self, key: str, options: Set[T]) -> T:
        value = self.get(key)
        matches = [x for x in options if x == value]
        if len(matches) == 0:
            raise ValueError(
                f"Expected configuration value {key} to be one of {options}, but found '{value}'."
            )
        return matches[0]

    def get_str_list(self, key: str) -> List[str]:
        value = self.get(key)
        if not isinstance(value, list):
            raise ValueError(
                f"Expected configuration value {key} to be an integer, but found type {type(value)}."
            )
        if any(not isinstance(x, str) for x in value):
            raise ValueError()
        return typing.cast(List[str], value)

    def get_float(self, key: str) -> float:
        value = self.get(key)
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return value
        raise ValueError(
            f"Expected configuration value {key} to be a number, but found type {type(value)}."
        )

    def get_positive_float(self, key: str) -> float:
        x = self.get_float(key)
        if x <= 0.0:
            raise ValueError(
                f"Expected configuration value {key} to be positive, but found value {x}."
            )
        return x

    def get_directory(self, key: str) -> Path:
        s = self.get_str(key)
        return parse_directory(s, missing_ok=True)

    def get_file(self, key: str) -> Path:
        s = self.get_str(key)
        return parse_file(s, missing_ok=True)

    def get_template(self, key: str) -> StringTemplate:
        template = self.get_str(key)
        return StringTemplate(template)

    def dump(self) -> Dict[str, object]:
        return self._data


# TODO: Move the slide style classes to a different file (where?)
# TODO: Enforce singleton pattern here?
class Config(BaseConfig):
    def __init__(
        self, args: ReccArgs, profile: Optional[str] = None, strict: bool = False
    ) -> None:
        self._args = args
        if profile is None:
            profile = get_active_profile()
        if profile is None:
            if strict:
                raise ValueError(f"{_PROFILE_SELECT_FILE.as_posix()} is missing.")
            else:
                profile = "foh" if platform.system() == "Darwin" else "mcr"
                activate_profile(profile)
        self._reader = ConfigFileReader(args=args, profile=profile, strict=strict)
        self.reload()

    def reload(self) -> None:
        with self._reader as reader:
            self.station: Literal["mcr", "foh"] = reader.get_enum(
                "station", {"mcr", "foh"}
            )

            # UI
            self.ui_theme: Literal["dark", "light"] = reader.get_enum(
                "ui.theme", {"dark", "light"}
            )

            # Folder structure
            self.downloads_dir = reader.get_directory("folder.downloads")
            self.home_dir = reader.get_directory("folder.home")
            self.assets_by_service_dir = reader.get_directory(
                "folder.assets_by_service"
            )
            self.assets_by_type_dir = reader.get_directory("folder.assets_by_type")
            self.images_dir = reader.get_directory("folder.images")
            self.videos_dir = reader.get_directory("folder.videos")
            self.log_dir = reader.get_directory("folder.logs")
            self.captions_dir = reader.get_directory("folder.captions")
            self.archived_assets_dir = reader.get_directory("folder.archived_assets")
            self.temp_assets_dir = reader.get_directory("folder.temporary_assets")

            # Logging
            self.check_credentials_log = reader.get_file("logging.check_credentials")
            self.check_credentials_webdriver_log_name = reader.get_str(
                "logging.check_credentials_webdriver_name"
            )
            self.download_assets_log = reader.get_file("logging.download_pco_assets")
            self.generate_slides_log = reader.get_file("logging.generate_slides")
            self.generate_slides_webdriver_log = reader.get_file(
                "logging.generate_slides_webdriver"
            )
            self.mcr_setup_log = reader.get_file("logging.mcr_setup")
            self.mcr_setup_webdriver_log = reader.get_file(
                "logging.mcr_setup_webdriver"
            )
            self.mcr_teardown_log = reader.get_file("logging.mcr_teardown")
            self.mcr_teardown_webdriver_log_name = reader.get_str(
                "logging.mcr_teardown_webdriver_name"
            )

            # Captions
            self.original_captions_file = reader.get_file("captions.original")
            self.final_captions_file = reader.get_file("captions.final")

            # BoxCast
            self.live_event_title = reader.get_str("boxcast.live_event_title")
            self.rebroadcast_title = reader.get_str("boxcast.rebroadcast_title")
            self.live_event_url_template = reader.get_template("boxcast.live_event_url")
            self.live_event_captions_tab_url_template = reader.get_template(
                "boxcast.live_event_captions_tab_url"
            )
            self.rebroadcast_setup_url_template = reader.get_template(
                "boxcast.rebroadcast_setup_url"
            )
            self.boxcast_edit_captions_url_template = reader.get_template(
                "boxcast.edit_captions_url"
            )
            self.captions_download_path_template = reader.get_template(
                "boxcast.captions_download_path"
            )

            # Planning Center
            self.pco_base_url = reader.get_str("planning_center.base_url")
            self.pco_services_base_url = reader.get_str(
                "planning_center.services_base_url"
            )
            self.pco_sunday_service_type_id = reader.get_str(
                "planning_center.sunday_service_type_id"
            )

            # Vimeo
            self.vimeo_new_video_hours = reader.get_positive_float(
                "vimeo.new_video_hours"
            )
            self.vimeo_retry_seconds = reader.get_positive_float("vimeo.retry_seconds")
            self.vimeo_captions_type = reader.get_str("vimeo.captions_type")
            self.vimeo_captions_language = reader.get_str("vimeo.captions_language")
            self.vimeo_captions_name = reader.get_str("vimeo.captions_name")
            self.vimeo_video_title_template = reader.get_template("vimeo.video_title")

            # vMix
            self.vmix_base_url = reader.get_str("vmix.base_url")
            self.vmix_kids_connection_list_key = reader.get_str(
                "vmix.kids_connection_list_key"
            )
            self.vmix_pre_stream_title_key = reader.get_str("vmix.pre_stream_title_key")
            self.vmix_speaker_title_key = reader.get_str("vmix.speaker_title_key")
            self.vmix_host_title_key = reader.get_str("vmix.host_title_key")
            self.vmix_extra_presenter_title_key = reader.get_str(
                "vmix.extra_presenter_title_key"
            )
            self.vmix_preset_file = reader.get_file("vmix.preset_path")

            # API
            self.timeout_seconds = reader.get_positive_float("api.timeout_seconds")
            self.timeout = timedelta(seconds=self.timeout_seconds)

            # Slides
            self.message_notes_filename = reader.get_str(
                "slides.message_notes_filename"
            )
            self.lyrics_filename = reader.get_str("slides.lyrics_filename")
            self.blueprints_filename = reader.get_str("slides.blueprints_filename")
            self.img_width = reader.get_positive_int("slides.image_width")
            self.img_height = reader.get_positive_int("slides.image_height")
            self.font_family = reader.get_str_list("slides.font_family")

            fsm = "slides.fullscreen_message"
            self.fullscreen_message_style = NoFooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_str(f"{fsm}.background"),
                body=Textbox(
                    bbox=Bbox.xywh(
                        x=reader.get_nonneg_int(f"{fsm}.body.x"),
                        y=reader.get_nonneg_int(f"{fsm}.body.y"),
                        w=reader.get_positive_int(f"{fsm}.body.width"),
                        h=reader.get_positive_int(f"{fsm}.body.height"),
                    ),
                    font=Font(
                        family=self.font_family,
                        style=reader.get_enum(f"{fsm}.body.font.style", _STYLES),
                        min_size=reader.get_positive_int(f"{fsm}.body.font.min_size"),
                        max_size=reader.get_positive_int(f"{fsm}.body.font.max_size"),
                    ),
                    horiz_align=reader.get_enum(
                        f"{fsm}.body.horiz_align", _HORIZ_ALIGNS
                    ),
                    vert_align=reader.get_enum(f"{fsm}.body.vert_align", _VERT_ALIGNS),
                    text_colour=reader.get_str(f"{fsm}.body.text_colour"),
                    bold=reader.get_bool(f"{fsm}.body.font.bold"),
                    line_spacing=reader.get_float(f"{fsm}.body.line_spacing"),
                ),
                shapes=[],
            )

            fss = "slides.fullscreen_scripture"
            self.fullscreen_scripture_style = FooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_str(f"{fss}.background"),
                body=Textbox(
                    bbox=Bbox.xywh(
                        x=reader.get_nonneg_int(f"{fss}.body.x"),
                        y=reader.get_nonneg_int(f"{fss}.body.y"),
                        w=reader.get_positive_int(f"{fss}.body.width"),
                        h=reader.get_positive_int(f"{fss}.body.height"),
                    ),
                    font=Font(
                        family=self.font_family,
                        style=reader.get_enum(f"{fss}.body.font.style", _STYLES),
                        min_size=reader.get_positive_int(f"{fss}.body.font.min_size"),
                        max_size=reader.get_positive_int(f"{fss}.body.font.max_size"),
                    ),
                    horiz_align=reader.get_enum(
                        f"{fss}.body.horiz_align", _HORIZ_ALIGNS
                    ),
                    vert_align=reader.get_enum(f"{fss}.body.vert_align", _VERT_ALIGNS),
                    text_colour=reader.get_str(f"{fss}.body.text_colour"),
                    bold=reader.get_bool(f"{fss}.body.font.bold"),
                    line_spacing=reader.get_float(f"{fss}.body.line_spacing"),
                ),
                footer=Textbox(
                    bbox=Bbox.xywh(
                        x=reader.get_nonneg_int(f"{fss}.footer.x"),
                        y=reader.get_nonneg_int(f"{fss}.footer.y"),
                        w=reader.get_positive_int(f"{fss}.footer.width"),
                        h=reader.get_positive_int(f"{fss}.footer.height"),
                    ),
                    font=Font(
                        family=self.font_family,
                        style=reader.get_enum(f"{fss}.footer.font.style", _STYLES),
                        min_size=reader.get_positive_int(f"{fss}.footer.font.min_size"),
                        max_size=reader.get_positive_int(f"{fss}.footer.font.max_size"),
                    ),
                    horiz_align=reader.get_enum(
                        f"{fss}.footer.horiz_align", _HORIZ_ALIGNS
                    ),
                    vert_align=reader.get_enum(
                        f"{fss}.footer.vert_align", _VERT_ALIGNS
                    ),
                    text_colour=reader.get_str(f"{fss}.footer.text_colour"),
                    bold=reader.get_bool(f"{fss}.footer.font.bold"),
                    line_spacing=reader.get_float(f"{fss}.footer.line_spacing"),
                ),
                shapes=[],
            )

            ltm = "slides.lowerthird_message"
            self._lowerthird_message_body = Textbox(
                bbox=Bbox.xywh(
                    x=reader.get_nonneg_int(f"{ltm}.body.x"),
                    y=reader.get_nonneg_int(f"{ltm}.body.y"),
                    w=reader.get_positive_int(f"{ltm}.body.width"),
                    h=reader.get_positive_int(f"{ltm}.body.height"),
                ),
                font=Font(
                    family=self.font_family,
                    style=reader.get_enum(f"{ltm}.body.font.style", _STYLES),
                    min_size=reader.get_positive_int(f"{ltm}.body.font.min_size"),
                    max_size=reader.get_positive_int(f"{ltm}.body.font.max_size"),
                ),
                horiz_align=reader.get_enum(f"{ltm}.body.horiz_align", _HORIZ_ALIGNS),
                vert_align=reader.get_enum(f"{ltm}.body.vert_align", _VERT_ALIGNS),
                text_colour=reader.get_str(f"{ltm}.body.text_colour"),
                bold=reader.get_bool(f"{ltm}.body.font.bold"),
                line_spacing=reader.get_float(f"{ltm}.body.line_spacing"),
            )
            self.lowerthird_message_style = NoFooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_str(f"{ltm}.background"),
                body=self._lowerthird_message_body,
                shapes=[
                    Rectangle(
                        bbox=Bbox.xywh(
                            x=reader.get_nonneg_int(f"{ltm}.rectangle.x"),
                            y=reader.get_nonneg_int(f"{ltm}.rectangle.y"),
                            w=reader.get_positive_int(f"{ltm}.rectangle.width"),
                            h=reader.get_positive_int(f"{ltm}.rectangle.height"),
                        ),
                        background_colour=reader.get_str(f"{ltm}.rectangle.colour"),
                    )
                ],
            )

            lts = "slides.lowerthird_scripture"
            self._lowerthird_scripture_body = Textbox(
                bbox=Bbox.xywh(
                    x=reader.get_nonneg_int(f"{lts}.body.x"),
                    y=reader.get_nonneg_int(f"{lts}.body.y"),
                    w=reader.get_positive_int(f"{lts}.body.width"),
                    h=reader.get_positive_int(f"{lts}.body.height"),
                ),
                font=Font(
                    family=self.font_family,
                    style=reader.get_enum(f"{lts}.body.font.style", _STYLES),
                    min_size=reader.get_positive_int(f"{lts}.body.font.min_size"),
                    max_size=reader.get_positive_int(f"{lts}.body.font.max_size"),
                ),
                horiz_align=reader.get_enum(f"{lts}.body.horiz_align", _HORIZ_ALIGNS),
                vert_align=reader.get_enum(f"{lts}.body.vert_align", _VERT_ALIGNS),
                text_colour=reader.get_str(f"{lts}.body.text_colour"),
                bold=reader.get_bool(f"{lts}.body.font.bold"),
                line_spacing=reader.get_float(f"{lts}.body.line_spacing"),
            )
            self._lowerthird_scripture_footer = Textbox(
                bbox=Bbox.xywh(
                    x=reader.get_nonneg_int(f"{lts}.footer.x"),
                    y=reader.get_nonneg_int(f"{lts}.footer.y"),
                    w=reader.get_positive_int(f"{lts}.footer.width"),
                    h=reader.get_positive_int(f"{lts}.footer.height"),
                ),
                font=Font(
                    family=self.font_family,
                    style=reader.get_enum(f"{lts}.footer.font.style", _STYLES),
                    min_size=reader.get_positive_int(f"{lts}.footer.font.min_size"),
                    max_size=reader.get_positive_int(f"{lts}.footer.font.max_size"),
                ),
                horiz_align=reader.get_enum(f"{lts}.footer.horiz_align", _HORIZ_ALIGNS),
                vert_align=reader.get_enum(f"{lts}.footer.vert_align", _VERT_ALIGNS),
                text_colour=reader.get_str(f"{lts}.footer.text_colour"),
                bold=reader.get_bool(f"{lts}.footer.font.bold"),
                line_spacing=reader.get_float(f"{lts}.footer.line_spacing"),
            )
            self.lowerthird_scripture_style = FooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_str(f"{lts}.background"),
                body=self._lowerthird_scripture_body,
                footer=self._lowerthird_scripture_footer,
                shapes=[
                    Rectangle(
                        bbox=Bbox.xywh(
                            x=reader.get_nonneg_int(f"{lts}.rectangle.x"),
                            y=reader.get_nonneg_int(f"{lts}.rectangle.y"),
                            w=reader.get_positive_int(f"{lts}.rectangle.width"),
                            h=reader.get_positive_int(f"{lts}.rectangle.height"),
                        ),
                        background_colour=reader.get_str(f"{lts}.rectangle.colour"),
                    )
                ],
            )

    @property
    def start_time(self) -> datetime:
        return self._args.start_time

    def fill_placeholders(self, text: str) -> str:
        return self._reader.fill_placeholders(text)

    def dump(self) -> Dict[str, object]:
        return self._reader.dump()
