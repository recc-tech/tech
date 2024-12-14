from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Set, Tuple

from PIL import ImageColor

ImgMode = Literal["1", "L", "RGB", "RGBA"]
HorizAlign = Literal["left", "center", "right"]
VertAlign = Literal["top", "center", "bottom"]
FontStyle = Literal["normal", "italic", "oblique"]


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
class Colour:
    r: int
    g: int
    b: int
    a: int

    @staticmethod
    def parse(colour: str) -> Colour:
        colour = colour.lower()
        match ImageColor.colormap.get(colour, colour):
            case (r, g, b):
                return Colour(r=r, g=g, b=b, a=255)
            case c:
                colour = c
        if re.fullmatch(r"#[0-9a-f]{6}", colour):
            return Colour(
                r=int(colour[1:3], 16),
                g=int(colour[3:5], 16),
                b=int(colour[5:7], 16),
                a=255,
            )
        if re.fullmatch(r"#([0-9a-f]{8})", colour):
            return Colour(
                r=int(colour[1:3], 16),
                g=int(colour[3:5], 16),
                b=int(colour[5:7], 16),
                a=int(colour[7:9], 16),
            )
        raise ValueError(f"Unrecognized colour '{colour}'.")

    @property
    def is_greyscale(self) -> bool:
        return self.r == self.g == self.b

    @property
    def is_black_and_white(self) -> bool:
        return self.is_greyscale and (
            self.r in {0, 255} and self.g in {0, 255} and self.b in {0, 255}
        )

    @property
    def mode(self) -> ImgMode:
        if self.a != 255:
            return "RGBA"
        if self.is_black_and_white:
            return "1"
        if self.is_greyscale:
            return "L"
        return "RGBA"

    def __str__(self) -> str:
        s = f"#{self.r:02x}{self.g:02x}{self.b:02x}"
        return s if self.a == 255 else f"{s}{self.a:02x}"


@dataclass(frozen=True)
class Textbox:
    bbox: Bbox
    font: Font
    horiz_align: HorizAlign
    vert_align: VertAlign
    text_colour: Colour
    bold: bool
    line_spacing: float

    @property
    def stroke_width(self) -> int:
        return 1 if self.bold else 0


@dataclass(frozen=True)
class Rectangle:
    bbox: Bbox
    background_colour: Colour


def max_mode(modes: Set[ImgMode]) -> ImgMode:
    """
    Choose the largest mode out of the given set, where RGBA > RGB > L > 1.
    In other words, if any of the given modes are RGBA, return RGBA.
    Otherwise, if any of them are RGB, return RGB.
    And so on.
    """
    if len(modes) == 0:
        raise ValueError("Empty set.")
    priority_by_mode: Dict[ImgMode, int] = {"RGBA": 1, "RGB": 2, "L": 3, "1": 4}
    sorted_modes = sorted(modes, key=lambda m: priority_by_mode[m])
    return sorted_modes[0]


@dataclass(frozen=True)
class NoFooterSlideStyle:
    width: int
    height: int
    background_colour: Colour
    body: Textbox
    shapes: List[Rectangle]

    @property
    def mode(self) -> ImgMode:
        m1: Set[ImgMode] = {self.background_colour.mode, self.body.text_colour.mode}
        m2: Set[ImgMode] = {r.background_colour.mode for r in self.shapes}
        return max_mode(m1.union(m2))

    @property
    def width_height(self) -> Tuple[int, int]:
        return (self.width, self.height)


@dataclass(frozen=True)
class FooterSlideStyle:
    width: int
    height: int
    background_colour: Colour
    body: Textbox
    footer: Textbox
    shapes: List[Rectangle]

    @property
    def mode(self) -> ImgMode:
        m1: Set[ImgMode] = {
            self.background_colour.mode,
            self.body.text_colour.mode,
            self.footer.text_colour.mode,
        }
        m2: Set[ImgMode] = {r.background_colour.mode for r in self.shapes}
        return max_mode(m1.union(m2))

    @property
    def width_height(self) -> Tuple[int, int]:
        return (self.width, self.height)
