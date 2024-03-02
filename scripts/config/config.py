from __future__ import annotations

import platform
import typing
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import TracebackType
from typing import Dict, List, Literal, Optional, Set, Tuple, Type, TypeVar

import tomli

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


# TODO: Add method to get positive number
# TODO: Add method to get directory without trailing slash
class ConfigFileReader(AbstractContextManager[object]):
    def __init__(self, strict: bool) -> None:
        self._strict = strict
        self._data = self._read_global_config()
        # IMPORTANT: read the local file second so that it overrides values
        # found in the global file
        self._data |= self._read_local_config()

    def _read_global_config(self) -> Dict[str, object]:
        global_file = Path(__file__).parent.joinpath("config.toml").resolve()
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

    def _read_local_config(self) -> Dict[str, object]:
        profile = self._read_profile()
        local_file = (
            Path(__file__).parent.joinpath("local", f"{profile}.toml").resolve()
        )
        try:
            with open(local_file, "rb") as f:
                return self._flatten(tomli.load(f))
        except FileNotFoundError as e:
            raise ValueError(
                f"Failed to read local config because {local_file.as_posix()} is missing."
            ) from e
        except Exception as e:
            raise ValueError(
                "Failed to read local config due to an unknown error."
            ) from e

    def _read_profile(self) -> str:
        profile_file = Path(__file__).parent.joinpath("active_profile.txt").resolve()
        try:
            profile = profile_file.read_text().strip()
        except FileNotFoundError:
            if self._strict:
                raise ValueError(
                    f"Failed to read local config because {profile_file.as_posix()} is missing."
                )
            profile = "foh" if platform.system() == "Darwin" else "mcr"
            try:
                profile_file.write_text(f"{profile}\n")
            except Exception as e:
                raise ValueError(
                    f"Failed to read local config because {profile_file.as_posix()} is missing and could not be created."
                ) from e
        return profile

    def _flatten(self, data: Dict[str, object]) -> Dict[str, object]:
        out_data: Dict[str, object] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                value = self._flatten(typing.cast(Dict[str, object], value))
                out_data |= {f"{key}.{k}": v for (k, v) in value.items()}
            else:
                out_data[key] = value
        return out_data

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
                f"The following configuration values are unknown: {unused_keys}"
            )

    def get_str(self, key: str) -> str:
        return self._get(key, str, "a string")

    def get_int(self, key: str) -> int:
        return self._get(key, int, "a whole number")

    def get_bool(self, key: str) -> bool:
        return self._get(key, bool, "true or false")

    def get_enum(self, key: str, options: Set[T]) -> T:
        self._is_read_by_key[key] = True
        value = self._data.get(key, None)
        if value is None:
            raise ValueError(f"Missing configuration value {key}.")
        matches = [x for x in options if x == value]
        if len(matches) == 0:
            raise ValueError(
                f"Expected configuration value {key} to be one of {options}, but found '{value}'."
            )
        return matches[0]

    def get_str_list(self, key: str) -> List[str]:
        self._is_read_by_key[key] = True
        value = self._data.get(key, None)
        if value is None:
            raise ValueError(f"Missing configuration value {key}.")
        if not isinstance(value, list):
            raise ValueError(
                f"Expected configuration value {key} to be an integer, but found type {type(value)}."
            )
        if any(not isinstance(x, str) for x in value):
            raise ValueError()
        return typing.cast(List[str], value)

    def get_float(self, key: str) -> float:
        self._is_read_by_key[key] = True
        value = self._data.get(key, None)
        if value is None:
            raise ValueError(f"Missing configuration value {key}.")
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return value
        raise ValueError(
            f"Expected configuration value {key} to be a number, but found type {type(value)}."
        )

    def _get(self, key: str, cls: Type[T], clsname: str) -> T:
        self._is_read_by_key[key] = True
        value = self._data.get(key, None)
        if value is None:
            raise ValueError(f"Missing configuration value {key}.")
        if not isinstance(value, cls):
            raise ValueError(
                f"Expected configuration value {key} to be {clsname}, but found type {type(value)}."
            )
        return value


# TODO: Add bidirectional association between this config and any Launch object
# that needs it
# TODO: Move the slide style classes to a different file (where?)
class Config:
    def __init__(self, strict: bool = False) -> None:
        self._strict = strict
        self.reload()

    def reload(self) -> None:
        with ConfigFileReader(strict=self._strict) as reader:
            self.pco_base_url = reader.get_str("planning_center.base_url")
            self.pco_services_base_url = reader.get_str(
                "planning_center.services_base_url"
            )
            self.pco_sunday_service_type_id = reader.get_str(
                "planning_center.sunday_service_type_id"
            )

            self.vimeo_new_video_hours = reader.get_float("vimeo.new_video_hours")
            self.vimeo_retry_seconds = reader.get_float("vimeo.retry_seconds")
            self.vimeo_captions_type = reader.get_str("vimeo.captions_type")
            self.vimeo_captions_language = reader.get_str("vimeo.captions_language")
            self.vimeo_captions_name = reader.get_str("vimeo.captions_name")

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

            self.timeout_seconds = reader.get_float("api.timeout_seconds")
            self.timeout = timedelta(seconds=self.timeout_seconds)

            self.img_width = reader.get_int("slides.image_width")
            self.img_height = reader.get_int("slides.image_height")
            self.font_family = reader.get_str_list("slides.font_family")

            fsm = "slides.fullscreen_message"
            self.fullscreen_message_style = NoFooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_str(f"{fsm}.background"),
                body=Textbox(
                    bbox=Bbox.xywh(
                        x=reader.get_int(f"{fsm}.body.x"),
                        y=reader.get_int(f"{fsm}.body.y"),
                        w=reader.get_int(f"{fsm}.body.width"),
                        h=reader.get_int(f"{fsm}.body.height"),
                    ),
                    font=Font(
                        family=self.font_family,
                        style=reader.get_enum(f"{fsm}.body.font.style", _STYLES),
                        min_size=reader.get_int(f"{fsm}.body.font.min_size"),
                        max_size=reader.get_int(f"{fsm}.body.font.max_size"),
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
                        x=reader.get_int(f"{fss}.body.x"),
                        y=reader.get_int(f"{fss}.body.y"),
                        w=reader.get_int(f"{fss}.body.width"),
                        h=reader.get_int(f"{fss}.body.height"),
                    ),
                    font=Font(
                        family=self.font_family,
                        style=reader.get_enum(f"{fss}.body.font.style", _STYLES),
                        min_size=reader.get_int(f"{fss}.body.font.min_size"),
                        max_size=reader.get_int(f"{fss}.body.font.max_size"),
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
                        x=reader.get_int(f"{fss}.footer.x"),
                        y=reader.get_int(f"{fss}.footer.y"),
                        w=reader.get_int(f"{fss}.footer.width"),
                        h=reader.get_int(f"{fss}.footer.height"),
                    ),
                    font=Font(
                        family=self.font_family,
                        style=reader.get_enum(f"{fss}.footer.font.style", _STYLES),
                        min_size=reader.get_int(f"{fss}.footer.font.min_size"),
                        max_size=reader.get_int(f"{fss}.footer.font.max_size"),
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
                    x=reader.get_int(f"{ltm}.body.x"),
                    y=reader.get_int(f"{ltm}.body.y"),
                    w=reader.get_int(f"{ltm}.body.width"),
                    h=reader.get_int(f"{ltm}.body.height"),
                ),
                font=Font(
                    family=self.font_family,
                    style=reader.get_enum(f"{ltm}.body.font.style", _STYLES),
                    min_size=reader.get_int(f"{ltm}.body.font.min_size"),
                    max_size=reader.get_int(f"{ltm}.body.font.max_size"),
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
                            x=reader.get_int(f"{ltm}.rectangle.x"),
                            y=reader.get_int(f"{ltm}.rectangle.y"),
                            w=reader.get_int(f"{ltm}.rectangle.width"),
                            h=reader.get_int(f"{ltm}.rectangle.height"),
                        ),
                        background_colour=reader.get_str(f"{ltm}.rectangle.colour"),
                    )
                ],
            )

            lts = "slides.lowerthird_scripture"
            self._lowerthird_scripture_body = Textbox(
                bbox=Bbox.xywh(
                    x=reader.get_int(f"{lts}.body.x"),
                    y=reader.get_int(f"{lts}.body.y"),
                    w=reader.get_int(f"{lts}.body.width"),
                    h=reader.get_int(f"{lts}.body.height"),
                ),
                font=Font(
                    family=self.font_family,
                    style=reader.get_enum(f"{lts}.body.font.style", _STYLES),
                    min_size=reader.get_int(f"{lts}.body.font.min_size"),
                    max_size=reader.get_int(f"{lts}.body.font.max_size"),
                ),
                horiz_align=reader.get_enum(f"{lts}.body.horiz_align", _HORIZ_ALIGNS),
                vert_align=reader.get_enum(f"{lts}.body.vert_align", _VERT_ALIGNS),
                text_colour=reader.get_str(f"{lts}.body.text_colour"),
                bold=reader.get_bool(f"{lts}.body.font.bold"),
                line_spacing=reader.get_float(f"{lts}.body.line_spacing"),
            )
            self._lowerthird_scripture_footer = Textbox(
                bbox=Bbox.xywh(
                    x=reader.get_int(f"{lts}.footer.x"),
                    y=reader.get_int(f"{lts}.footer.y"),
                    w=reader.get_int(f"{lts}.footer.width"),
                    h=reader.get_int(f"{lts}.footer.height"),
                ),
                font=Font(
                    family=self.font_family,
                    style=reader.get_enum(f"{lts}.footer.font.style", _STYLES),
                    min_size=reader.get_int(f"{lts}.footer.font.min_size"),
                    max_size=reader.get_int(f"{lts}.footer.font.max_size"),
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
                            x=reader.get_int(f"{lts}.rectangle.x"),
                            y=reader.get_int(f"{lts}.rectangle.y"),
                            w=reader.get_int(f"{lts}.rectangle.width"),
                            h=reader.get_int(f"{lts}.rectangle.height"),
                        ),
                        background_colour=reader.get_str(f"{lts}.rectangle.colour"),
                    )
                ],
            )
