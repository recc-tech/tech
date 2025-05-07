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
from autochecklist import BaseConfig

from .image_style import (
    Bbox,
    Colour,
    Font,
    FontStyle,
    FooterSlideStyle,
    HorizAlign,
    NoFooterSlideStyle,
    Rectangle,
    Textbox,
    VertAlign,
)

T = TypeVar("T")

_HORIZ_ALIGNS: Set[HorizAlign] = {"left", "center", "right"}
_VERT_ALIGNS: Set[VertAlign] = {"top", "center", "bottom"}
_STYLES: Set[FontStyle] = {"normal", "italic", "oblique"}

_CONFIG_DIR = Path(__file__).resolve().parent.parent
_PROFILE_SELECT_FILE = _CONFIG_DIR.joinpath("active_profile.txt").resolve()
_PROFILES_DIR = _CONFIG_DIR.joinpath("profiles")


def locate_global_config() -> Path:
    return _CONFIG_DIR.joinpath("config.toml").resolve()


def locate_profile(profile: str) -> Path:
    return _PROFILES_DIR.joinpath(f"{profile}.toml").resolve()


def get_active_profile() -> Optional[str]:
    try:
        return _PROFILE_SELECT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def activate_profile(profile: str) -> None:
    f = locate_profile(profile)
    if not f.is_file():
        raise ValueError(
            f"There is no profile called '{profile}' (expected to find it at {f.as_posix()})."
        )
    try:
        _PROFILE_SELECT_FILE.write_text(f"{profile}\n", encoding="utf-8")
    except Exception as e:
        raise ValueError(
            f"{_PROFILE_SELECT_FILE.as_posix()} is missing and could not be created."
        ) from e


def get_default_profile() -> str:
    return "foh" if platform.system() == "Darwin" else "mcr"


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


def _flatten(data: Dict[str, object]) -> Dict[str, object]:
    out_data: Dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            value = _flatten(typing.cast(Dict[str, object], value))
            out_data |= {f"{key}.{k}": v for (k, v) in value.items()}
        else:
            out_data[key] = value
    return out_data


def _resolve(raw_data: Dict[str, object]) -> Tuple[Dict[str, object], Set[str]]:
    resolved_data: Dict[str, object] = {}
    toplevel_keys: Set[str] = set(raw_data.keys())
    for k, v in raw_data.items():
        if isinstance(v, str):
            try:
                (v, deps) = _fill_placeholders(raw_data, v, [k])
            except Exception as e:
                raise ValueError(
                    f"Failed to fill placeholders in configuration value {k}."
                ) from e
            resolved_data[k] = v
            toplevel_keys -= deps
        else:
            resolved_data[k] = v
    return (resolved_data, toplevel_keys)


def _fill_placeholders(
    data: Dict[str, object], template: str, history: List[str]
) -> Tuple[str, Set[str]]:
    deps: Set[str] = set()
    while True:
        start = template.find("%{")
        end = template.find("}%")
        if start < 0 and end < 0:
            return (template, deps)
        elif start < 0:
            raise ValueError(f"Mismatched %{{ in '{template}'.")
        elif end < 0 or end < start:
            raise ValueError(f"Mismatched }}% in '{template}'.")
        else:
            placeholder_key = template[start + 2 : end]
            v, d = _get_and_fill(data, placeholder_key, history)
            placeholder = "%{" + placeholder_key + "}%"
            template = template.replace(placeholder, v)
            deps |= d
            deps.add(placeholder_key)


def _get_and_fill(
    data: Dict[str, object], key: str, history: List[str]
) -> Tuple[str, Set[str]]:
    if key in history:
        i = history.index(key)
        circ = history[i:] + [key]
        raise ValueError(f"Circular reference in configuration: {' --> '.join(circ)}.")
    v = data.get(key)
    if v is None:
        raise ValueError(f"Missing configuration value {key}.")
    if isinstance(v, str):
        return _fill_placeholders(data, v, history + [key])
    else:
        return (str(v), set())


def _read_global_config() -> Dict[str, object]:
    global_file = locate_global_config()
    try:
        with open(global_file, "rb") as f:
            return _flatten(tomli.load(f))
    except FileNotFoundError as e:
        raise ValueError(
            f"Failed to read global config because {global_file.as_posix()} is missing."
        ) from e
    except Exception as e:
        raise ValueError("Failed to read global config due to an unknown error.") from e


def _read_local_config(profile: str) -> Dict[str, object]:
    local_file = locate_profile(profile)
    try:
        with open(local_file, "rb") as f:
            return _flatten(tomli.load(f))
    except FileNotFoundError as e:
        raise ValueError(
            f"There is no profile called '{profile}' (expected to find it at {local_file.as_posix()})."
        ) from e
    except Exception as e:
        raise ValueError("Failed to read local config due to an unknown error.") from e


class ConfigReader(AbstractContextManager[object]):
    def __init__(self, raw_data: Dict[str, object], strict: bool) -> None:
        self._strict = strict
        self._is_read_by_key: Dict[str, bool] = {}
        (self._data, self._toplevel_keys) = _resolve(raw_data)

    def __enter__(self) -> ConfigReader:
        self._is_read_by_key = {key: False for key in self._toplevel_keys}
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
        # Don't worry if some of the args aren't used
        unused_keys -= {k for k in unused_keys if k.startswith("args.")}
        if len(unused_keys) > 0:
            raise ValueError(
                f"The following configuration values are unrecognized: {unused_keys}."
            )

    def fill_placeholders(self, template: str) -> str:
        v, _ = _fill_placeholders(self._data, template, [])
        return v

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

    def get_dict(self, key: str) -> Dict[str, object]:
        d: Dict[str, object] = {}
        for k, v in self._data.items():
            if k.startswith(f"{key}."):
                self._is_read_by_key[k] = True
                d[k.removeprefix(f"{key}.")] = v
        return d

    def get_str_dict(self, key: str) -> Dict[str, str]:
        obj_dict = self.get_dict(key)
        d: Dict[str, str] = {}
        for k, v in obj_dict.items():
            if not isinstance(v, str):
                raise ValueError(
                    f"Expected configuration value {k} to be a string, but found type {type(v)}."
                )
            d[k] = v
        return d

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

    def get_colour(self, key: str) -> Colour:
        c = self.get_str(key)
        return Colour.parse(c)

    def dump(self) -> Dict[str, object]:
        return self._data


class Config(BaseConfig):
    __instantiated = False

    def __init__(
        self,
        args: ReccArgs,
        profile: Optional[str] = None,
        strict: bool = False,
        allow_multiple_only_for_testing: bool = False,
        create_dirs: bool = False,
    ) -> None:
        if Config.__instantiated and not allow_multiple_only_for_testing:
            raise ValueError("Attempt to instantiate multiple Config objects.")
        Config.__instantiated = True
        self._args = args
        self._strict = strict
        if profile is None:
            profile = get_active_profile()
        if profile is None:
            if strict:
                raise ValueError(f"{_PROFILE_SELECT_FILE.as_posix()} is missing.")
            else:
                profile = get_default_profile()
                activate_profile(profile)
        self._profile = profile
        self.reload(create_dirs=create_dirs)

    def reload(self, create_dirs: bool = False) -> None:
        profile = self._profile
        data = _read_global_config()
        # IMPORTANT: read the local file second so that it overrides values
        # found in the global file
        data |= _read_local_config(profile)
        data |= _flatten({"args": self._args.dump()})
        self._reader = ConfigReader(raw_data=data, strict=self._strict)
        with self._reader as reader:
            self.station: Literal["mcr", "foh", "pi"] = reader.get_enum(
                "station", {"mcr", "foh", "pi"}
            )

            # UI
            self.ui_theme: Literal["dark", "light"] = reader.get_enum(
                "ui.theme", {"dark", "light"}
            )
            self.icon = reader.get_file("ui.icon")

            # Folder structure
            # (Some folders should already exist in production, but create them
            # so that the tests pass even after cleaning up the repo)
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
            self.plan_summaries_dir = reader.get_directory("folder.plan_summaries")
            if create_dirs:
                self.home_dir.mkdir(exist_ok=True, parents=True)
                self.assets_by_service_dir.mkdir(exist_ok=True, parents=True)
                self.assets_by_type_dir.mkdir(exist_ok=True, parents=True)
                self.images_dir.mkdir(exist_ok=True, parents=True)
                self.videos_dir.mkdir(exist_ok=True, parents=True)
                self.log_dir.mkdir(exist_ok=True, parents=True)
                self.captions_dir.mkdir(exist_ok=True, parents=True)
                self.archived_assets_dir.mkdir(exist_ok=True, parents=True)
                self.plan_summaries_dir.mkdir(exist_ok=True, parents=True)

            # Logging
            self.check_credentials_log = reader.get_file("logging.check_credentials")
            self.download_assets_log = reader.get_file("logging.download_pco_assets")
            self.generate_slides_log = reader.get_file("logging.generate_slides")
            self.launch_apps_log = reader.get_file("logging.launch_apps")
            self.mcr_setup_log = reader.get_file("logging.mcr_setup")
            self.mcr_teardown_log = reader.get_file("logging.mcr_teardown")
            self.summarize_plan_log = reader.get_file("logging.summarize_plan")
            self.manual_test_log = reader.get_file("logging.manual_test")
            self.boxcast_verbose_logging = reader.get_bool(
                "logging.boxcast_verbose_logging"
            )

            # Captions
            self.original_captions_file = reader.get_file("captions.original")
            self.auto_edited_captions_file = reader.get_file("captions.auto_edited")
            self.final_captions_file = reader.get_file("captions.final")
            self.caption_substitutions = reader.get_str_dict("captions.substitutions")

            # GitHub
            self.github_api_repo_url = reader.get_str("github.api_repo_url")

            # Church Online Platform
            self.cop_host_url = reader.get_str("cop.host_url")

            # BoxCast
            self.boxcast_base_url = reader.get_str("boxcast.base_url")
            self.boxcast_auth_base_url = reader.get_str("boxcast.auth_base_url")
            self.boxcast_broadcasts_html_url = reader.get_str(
                "boxcast.broadcasts_html_url"
            )
            self.rebroadcast_title = reader.get_str("boxcast.rebroadcast_title")
            self.upload_captions_retry_delay = timedelta(
                seconds=reader.get_float("boxcast.upload_captions_retry_delay")
            )
            self.generate_captions_retry_delay = timedelta(
                seconds=reader.get_float("boxcast.generate_captions_retry_delay")
            )
            self.max_captions_wait_time = timedelta(
                minutes=reader.get_float("boxcast.max_captions_wait_time")
            )

            # Planning Center
            self.pco_base_url = reader.get_str("planning_center.base_url")
            self.pco_services_base_url = reader.get_str(
                "planning_center.services_base_url"
            )
            self.live_view_url = reader.get_template("planning_center.live_view_url")
            self.pco_skipped_service_types = set(
                reader.get_str_list("planning_center.skipped_service_types")
            )
            self.kids_video_regex = reader.get_str("planning_center.kids_video_regex")
            self.sermon_notes_regex = reader.get_str(
                "planning_center.sermon_notes_regex"
            )
            self.announcements_video_regex = reader.get_str(
                "planning_center.announcements_video_regex"
            )
            self.default_speaker_name = reader.get_str(
                "planning_center.default_speaker_name"
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
            self.vimeo_user_id = reader.get_str("vimeo.user_id")

            # vMix
            self.vmix_base_url = reader.get_str("vmix.base_url")
            self.vmix_kids_connection_list_key = reader.get_str(
                "vmix.kids_connection_list_key"
            )
            self.vmix_announcements_list_key = reader.get_str(
                "vmix.livestream_announcements_list_key"
            )
            self.vmix_pre_stream_title_key = reader.get_str("vmix.pre_stream_title_key")
            self.vmix_speaker_title_key = reader.get_str("vmix.speaker_title_key")
            self.vmix_host1_title_key = reader.get_str("vmix.host1_title_key")
            self.vmix_host2_title_key = reader.get_str("vmix.host2_title_key")
            self.vmix_preset_dir = reader.get_directory("vmix.preset_dir")
            self.vmix_preset_file = reader.get_file("vmix.preset_path")

            # API
            self.timeout_seconds = reader.get_positive_float("api.timeout_seconds")
            self.timeout = timedelta(seconds=self.timeout_seconds)

            # Plan Summaries
            self.plan_summary_note_categories = set(
                reader.get_str_list("plan_summary.note_categories")
            )
            self.announcements_to_ignore = {
                a.lower()
                for a in reader.get_str_list("plan_summary.announcements_to_ignore")
            }

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
                background_colour=reader.get_colour(f"{fsm}.background"),
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
                    text_colour=reader.get_colour(f"{fsm}.body.text_colour"),
                    bold=reader.get_bool(f"{fsm}.body.font.bold"),
                    line_spacing=reader.get_float(f"{fsm}.body.line_spacing"),
                ),
                shapes=[],
            )

            fss = "slides.fullscreen_scripture"
            self.fullscreen_scripture_style = FooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_colour(f"{fss}.background"),
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
                    text_colour=reader.get_colour(f"{fss}.body.text_colour"),
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
                    text_colour=reader.get_colour(f"{fss}.footer.text_colour"),
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
                text_colour=reader.get_colour(f"{ltm}.body.text_colour"),
                bold=reader.get_bool(f"{ltm}.body.font.bold"),
                line_spacing=reader.get_float(f"{ltm}.body.line_spacing"),
            )
            self.lowerthird_message_style = NoFooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_colour(f"{ltm}.background"),
                body=self._lowerthird_message_body,
                shapes=[
                    Rectangle(
                        bbox=Bbox.xywh(
                            x=reader.get_nonneg_int(f"{ltm}.rectangle.x"),
                            y=reader.get_nonneg_int(f"{ltm}.rectangle.y"),
                            w=reader.get_positive_int(f"{ltm}.rectangle.width"),
                            h=reader.get_positive_int(f"{ltm}.rectangle.height"),
                        ),
                        background_colour=reader.get_colour(f"{ltm}.rectangle.colour"),
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
                text_colour=reader.get_colour(f"{lts}.body.text_colour"),
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
                text_colour=reader.get_colour(f"{lts}.footer.text_colour"),
                bold=reader.get_bool(f"{lts}.footer.font.bold"),
                line_spacing=reader.get_float(f"{lts}.footer.line_spacing"),
            )
            self.lowerthird_scripture_style = FooterSlideStyle(
                width=self.img_width,
                height=self.img_height,
                background_colour=reader.get_colour(f"{lts}.background"),
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
                        background_colour=reader.get_colour(f"{lts}.rectangle.colour"),
                    )
                ],
            )

    @property
    def start_time(self) -> datetime:
        return self._args.start_time

    @property
    def download_announcements_vid(self) -> bool:
        return self.station == "mcr"

    @property
    def download_kids_vid(self) -> bool:
        return self.station == "mcr"

    @property
    def download_sermon_notes(self) -> bool:
        return self.station == "mcr"

    @property
    def if_announcements_vid_missing(self) -> Literal["ok", "warn", "error"]:
        return "error"

    @property
    def if_kids_vid_missing(self) -> Literal["ok", "warn", "error"]:
        return "error"

    @property
    def if_sermon_notes_missing(self) -> Literal["ok", "warn", "error"]:
        return "warn"

    def fill_placeholders(self, text: str) -> str:
        return self._reader.fill_placeholders(text)

    def dump(self) -> Dict[str, object]:
        return self._reader.dump()
