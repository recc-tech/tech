from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Tuple

from autochecklist import Messenger, ProblemLevel
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

IMG_WIDTH = 1920
IMG_HEIGHT = 1080
OUTER_MARGIN = 100
INNER_MARGIN = 25
FONT_FACE = "calibri.ttf"


@dataclass
class SlideBlueprint:
    body_text: str
    footer_text: str
    name: str

    def with_name(self, new_name: str) -> SlideBlueprint:
        """
        Returns a new `SlideBlueprint` with the given name.
        """
        return SlideBlueprint(
            body_text=self.body_text, footer_text=self.footer_text, name=new_name
        )


@dataclass
class Slide:
    image: Image.Image
    name: str

    def save(self, directory: Path):
        path = directory.joinpath(self.name)
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png")
        self.image.save(path, format="PNG")


@dataclass
class _Bbox:
    left: int
    top: int
    right: int
    bottom: int

    def get_horizontal_centre(self) -> float:
        return self.left + (self.right - self.left) / 2

    def get_vertical_centre(self) -> float:
        return self.top + (self.bottom - self.top) / 2

    def get_width(self) -> int:
        return self.right - self.left

    def get_height(self) -> int:
        return self.bottom - self.top


class SlideGenerator:
    def __init__(self, messenger: Messenger):
        self._messenger = messenger

    def generate_fullscreen_slides(
        self, blueprints: List[SlideBlueprint]
    ) -> List[Slide]:
        # ImageFont.truetype opens a font file and keeps it open. Load the
        # fonts once here instead of loading them in
        # _generate_fullscreen_slide_with[out]_footer to avoid opening too many
        # files.
        # https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.truetype
        body_font = ImageFont.truetype(FONT_FACE, size=72)
        footer_font = ImageFont.truetype(FONT_FACE, size=60)

        return [
            self._generate_fullscreen_slide_with_footer(
                b, body_font=body_font, footer_font=footer_font
            )
            if b.footer_text
            else self._generate_fullscreen_slide_without_footer(b, font=body_font)
            for b in blueprints
        ]

    def generate_lower_third_slide(
        self, blueprints: List[SlideBlueprint], show_backdrop: bool
    ) -> List[Slide]:
        body_font = ImageFont.truetype(FONT_FACE, size=48)
        footer_font = ImageFont.truetype(FONT_FACE, size=44)
        no_footer_font = ImageFont.truetype(FONT_FACE, size=56)

        return [
            self._generate_lower_third_slide_with_footer(
                b, show_backdrop, body_font=body_font, footer_font=footer_font
            )
            if b.footer_text
            else self._generate_lower_third_slide_without_footer(
                b, show_backdrop, font=no_footer_font
            )
            for b in blueprints
        ]

    def _generate_fullscreen_slide_with_footer(
        self, input: SlideBlueprint, body_font: FreeTypeFont, footer_font: FreeTypeFont
    ) -> Slide:
        img = Image.new(mode="L", size=(IMG_WIDTH, IMG_HEIGHT), color="white")
        draw = ImageDraw.Draw(img)
        self._draw_text(
            draw=draw,
            text=input.body_text,
            bbox=_Bbox(
                left=OUTER_MARGIN,
                top=OUTER_MARGIN,
                right=IMG_WIDTH - OUTER_MARGIN,
                bottom=IMG_HEIGHT - 3 * OUTER_MARGIN,
            ),
            horiz_align="left",
            vert_align="top",
            font=body_font,
            foreground="#333333",
            stroke_width=1,  # bold
            line_spacing=1.75,
            slide_name=input.name,
        )
        self._draw_text(
            draw=draw,
            text=input.footer_text,
            bbox=_Bbox(
                OUTER_MARGIN,
                IMG_HEIGHT - 2 * OUTER_MARGIN,
                IMG_WIDTH - OUTER_MARGIN,
                IMG_HEIGHT - OUTER_MARGIN,
            ),
            horiz_align="right",
            vert_align="center",
            font=footer_font,
            foreground="dimgrey",
            stroke_width=0,
            line_spacing=1.75,
            slide_name=input.name,
        )
        return Slide(image=img, name=input.name)

    def _generate_fullscreen_slide_without_footer(
        self, input: SlideBlueprint, font: FreeTypeFont
    ) -> Slide:
        img = Image.new(mode="L", size=(IMG_WIDTH, IMG_HEIGHT), color="white")
        draw = ImageDraw.Draw(img)
        self._draw_text(
            draw=draw,
            text=input.body_text,
            bbox=_Bbox(
                OUTER_MARGIN,
                OUTER_MARGIN,
                IMG_WIDTH - OUTER_MARGIN,
                IMG_HEIGHT - OUTER_MARGIN,
            ),
            horiz_align="center",
            vert_align="center",
            font=font,
            foreground="#333333",
            stroke_width=1,  # bold
            line_spacing=1.75,
            slide_name=input.name,
        )
        return Slide(image=img, name=input.name)

    def _generate_lower_third_slide_with_footer(
        self,
        blueprint: SlideBlueprint,
        show_backdrop: bool,
        body_font: FreeTypeFont,
        footer_font: FreeTypeFont,
    ) -> Slide:
        img = Image.new(mode="RGBA", size=(IMG_WIDTH, IMG_HEIGHT), color="#00000000")
        draw = ImageDraw.Draw(img)

        if show_backdrop:
            draw.rectangle(
                (
                    0,
                    (IMG_HEIGHT * 2) // 3 - INNER_MARGIN,
                    IMG_WIDTH,
                    IMG_HEIGHT - OUTER_MARGIN + INNER_MARGIN,
                ),
                fill="#00000088",
            )
        self._draw_text(
            draw=draw,
            text=blueprint.body_text,
            bbox=_Bbox(
                left=OUTER_MARGIN,
                top=(IMG_HEIGHT * 2) // 3,
                right=IMG_WIDTH - OUTER_MARGIN,
                bottom=IMG_HEIGHT - OUTER_MARGIN - 50,
            ),
            horiz_align="left",
            vert_align="top",
            font=body_font,
            foreground="white",
            stroke_width=1,
            line_spacing=1.5,
            slide_name=blueprint.name,
        )
        self._draw_text(
            draw=draw,
            text=blueprint.footer_text,
            bbox=_Bbox(
                left=OUTER_MARGIN,
                top=IMG_HEIGHT - OUTER_MARGIN - 40,
                right=IMG_WIDTH - OUTER_MARGIN,
                bottom=IMG_HEIGHT - OUTER_MARGIN,
            ),
            horiz_align="right",
            vert_align="center",
            font=footer_font,
            foreground="#DDDDDD",
            stroke_width=0,
            line_spacing=1,
            slide_name=blueprint.name,
        )

        return Slide(image=img, name=blueprint.name)

    def _generate_lower_third_slide_without_footer(
        self, blueprint: SlideBlueprint, show_backdrop: bool, font: FreeTypeFont
    ) -> Slide:
        img = Image.new(mode="RGBA", size=(IMG_WIDTH, IMG_HEIGHT), color="#00000000")
        draw = ImageDraw.Draw(img)

        if show_backdrop:
            draw.rectangle(
                (
                    0,
                    (IMG_HEIGHT * 2) // 3 - INNER_MARGIN,
                    IMG_WIDTH,
                    IMG_HEIGHT - OUTER_MARGIN + INNER_MARGIN,
                ),
                fill="#00000088",
            )

        self._draw_text(
            draw=draw,
            text=blueprint.body_text,
            bbox=_Bbox(
                left=OUTER_MARGIN,
                top=(IMG_HEIGHT * 2) // 3,
                right=IMG_WIDTH - OUTER_MARGIN,
                bottom=IMG_HEIGHT - OUTER_MARGIN,
            ),
            horiz_align="center",
            vert_align="center",
            font=font,
            foreground="white",
            stroke_width=1,
            line_spacing=2,
            slide_name=blueprint.name,
        )

        return Slide(image=img, name=blueprint.name)

    def _draw_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        bbox: _Bbox,
        horiz_align: Literal["left", "center", "right"],
        vert_align: Literal["top", "center", "bottom"],
        font: FreeTypeFont,
        foreground: str,
        stroke_width: int,
        line_spacing: float,
        slide_name: str,
    ):
        wrapped_text = _wrap_text(text, bbox.get_width(), font, stroke_width)

        anchor_horiz = (
            "l" if horiz_align == "left" else "r" if horiz_align == "right" else "m"
        )
        anchor_vert = (
            "a" if vert_align == "top" else "d" if vert_align == "bottom" else "m"
        )
        anchor = f"{anchor_horiz}{anchor_vert}"

        x = (
            bbox.left
            if horiz_align == "left"
            else bbox.right
            if horiz_align == "right"
            else bbox.get_horizontal_centre()
        )
        y = (
            bbox.top
            if vert_align == "top"
            else bbox.bottom
            if vert_align == "bottom"
            else bbox.get_vertical_centre()
        )
        xy = (x, y)

        line_height = _get_font_bbox("A", font, stroke_width).get_height()
        textbbox = _Bbox(
            *draw.textbbox(
                xy=xy,
                text=wrapped_text,
                font=font,
                spacing=line_height * (line_spacing - 1),
                align=horiz_align,
                anchor=anchor,
                stroke_width=stroke_width,
            )
        )
        if (
            textbbox.get_height() > bbox.get_height()
            or textbbox.get_width() > bbox.get_width()
        ):
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"The text in slide '{slide_name}' does not fit within the normal text box.",
            )
        draw.text(  # type: ignore
            xy=xy,
            text=wrapped_text,
            fill=foreground,
            font=font,
            spacing=line_height * (line_spacing - 1),
            align=horiz_align,
            anchor=anchor,
            stroke_width=stroke_width,
            stroke_fill=foreground,
        )


def _wrap_text(text: str, max_width: int, font: FreeTypeFont, stroke_width: int) -> str:
    text = text.strip().replace("\r\n", "\n")
    # Keep line breaks that the user manually chose
    lines = [re.sub(r"\s+", " ", line) for line in text.split("\n") if line]
    return "\n".join(
        [_wrap_line(line, max_width, font, stroke_width) for line in lines]
    )


def _wrap_line(line: str, max_width: int, font: FreeTypeFont, stroke_width: int) -> str:
    words = [w for w in line.split(" ") if w]
    output_lines: List[str] = []
    while words:
        (wrapped_line, words) = _extract_max_prefix(
            words, max_width, font, stroke_width
        )
        output_lines.append(wrapped_line)
    return "\n".join(output_lines)


def _extract_max_prefix(
    words: List[str], max_width: int, font: FreeTypeFont, stroke_width: int
) -> Tuple[str, List[str]]:
    """
    Return as many words as can fit on one line, along with the remaining words. At least one word will be taken regardless of its length.
    """
    if not words:
        raise ValueError("No words provided.")
    words = list(words)  # Avoid side effects
    output = words[0]
    words = words[1:]
    while True:
        if not words:
            break
        next_word = words[0]
        longer_output = f"{output} {next_word}"
        width = _get_font_bbox(longer_output, font, stroke_width).get_width()
        if width > max_width:
            break
        else:
            output = longer_output
            words = words[1:]
    return (output, words)


def _get_font_bbox(text: str, font: FreeTypeFont, stroke_width: int) -> _Bbox:
    return _Bbox(*font.getbbox(text, stroke_width=stroke_width))  # type: ignore
