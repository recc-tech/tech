from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Tuple

ImgMode = Literal["1", "L", "RGB", "RGBA"]
HorizAlign = Literal["left", "center", "right"]
VertAlign = Literal["top", "center", "bottom"]


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
    style: Literal["normal", "italic", "oblique"]
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


# TODO: Load from file
# TODO: Add bidirectional association between this config and any Launch object
# that needs it
class SlidesConfig:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self._fullscreen_message_style = NoFooterSlideStyle(
            width=self.img_width,
            height=self.img_height,
            background_colour="white",
            body=Textbox(
                bbox=Bbox.xywh(x=100, y=100, w=1720, h=880),
                font=Font(
                    family=self.font_family, style="normal", min_size=36, max_size=72
                ),
                horiz_align="center",
                vert_align="center",
                text_colour="#333333",
                bold=True,
                line_spacing=1.75,
            ),
            shapes=[],
        )

        self._fullscreen_scripture_style = FooterSlideStyle(
            width=self.img_width,
            height=self.img_height,
            background_colour="white",
            body=Textbox(
                bbox=Bbox.xywh(x=100, y=100, w=1720, h=680),
                font=Font(
                    family=self.font_family, style="normal", min_size=36, max_size=72
                ),
                horiz_align="left",
                vert_align="top",
                text_colour="#333333",
                bold=True,
                line_spacing=1.75,
            ),
            footer=Textbox(
                bbox=Bbox.xywh(x=100, y=880, w=1720, h=100),
                font=Font(
                    family=self.font_family, style="oblique", min_size=30, max_size=60
                ),
                horiz_align="right",
                vert_align="center",
                text_colour="dimgrey",
                bold=False,
                line_spacing=1.75,
            ),
            shapes=[],
        )

        # Lower-third message style
        self._lowerthird_message_body = Textbox(
            bbox=Bbox.xywh(x=25, y=850, w=1870, h=200),
            font=Font(
                family=self.font_family,
                style="normal",
                min_size=24,
                max_size=48,
            ),
            horiz_align="center",
            vert_align="center",
            text_colour="white",
            bold=True,
            line_spacing=2,
        )
        self._lowerthird_message_style = NoFooterSlideStyle(
            width=self.img_width,
            height=self.img_height,
            background_colour="#00000000",
            body=self._lowerthird_message_body,
            shapes=[
                Rectangle(
                    bbox=Bbox.xywh(x=0, y=850, w=self.img_width, h=200),
                    background_colour="#00000088",
                )
            ],
        )

        # Lower-third scripture style
        self._lowerthird_scripture_body = Textbox(
            bbox=Bbox.xywh(x=0, y=825, w=1870, h=160),
            font=Font(
                family=self.font_family, style="normal", min_size=24, max_size=48
            ),
            horiz_align="left",
            vert_align="top",
            text_colour="white",
            bold=True,
            line_spacing=1.5,
        )
        self._lowerthird_scripture_footer = Textbox(
            bbox=Bbox.xywh(x=25, y=985, w=1870, h=50),
            font=Font(
                family=self.font_family, style="oblique", min_size=20, max_size=40
            ),
            horiz_align="right",
            vert_align="center",
            text_colour="#DDDDDD",
            bold=False,
            line_spacing=1,
        )
        self._lowerthird_scripture_style = FooterSlideStyle(
            width=self.img_width,
            height=self.img_height,
            background_colour="#00000000",
            body=self._lowerthird_scripture_body,
            footer=self._lowerthird_scripture_footer,
            shapes=[
                Rectangle(
                    bbox=Bbox.xywh(x=0, y=825, w=self.img_width, h=225),
                    background_colour="#00000088",
                )
            ],
        )

    @property
    def img_width(self) -> int:
        return 1920

    @property
    def img_height(self) -> int:
        return 1080

    @property
    def font_family(self) -> List[str]:
        return ["Helvetica", "Calibri", "sans-serif"]

    @property
    def fullscreen_message_style(self) -> NoFooterSlideStyle:
        return self._fullscreen_message_style

    @property
    def fullscreen_scripture_style(self) -> FooterSlideStyle:
        return self._fullscreen_scripture_style

    @property
    def lowerthird_message_style(self) -> NoFooterSlideStyle:
        return self._lowerthird_message_style

    @property
    def lowerthird_scripture_style(self) -> FooterSlideStyle:
        return self._lowerthird_scripture_style
