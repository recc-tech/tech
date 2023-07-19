from dataclasses import dataclass
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

IMG_WIDTH = 1640
IMG_HEIGHT = 924
MARGIN = 100
FONT_FACE = "calibri.ttf"


@dataclass
class SlideInput:
    body_text: str
    footer_text: str
    name: str = ""


@dataclass
class SlideOutput:
    image: Image.Image
    name: str


def generate_fullscreen_slides(slides: List[SlideInput]) -> List[SlideOutput]:
    return [
        _generate_fullscreen_slide_with_footer(s)
        if s.footer_text
        else _generate_fullscreen_slide_without_footer(s)
        for s in slides
    ]


def generate_lower_thirds_slide():
    # TODO: Make lower thirds slides
    # NOTE: To center the text, call draw.text() with align="center", anchor="mm", and xy set to the middle of the desired bounding box
    ...


# TODO: Warn the user or something if the text overflows the bounding box?
def _generate_fullscreen_slide_with_footer(input: SlideInput) -> SlideOutput:
    colour_mode = "L"
    background = "white"
    main_bbox = (MARGIN, MARGIN, IMG_WIDTH - MARGIN, IMG_HEIGHT - 3 * MARGIN)
    main_foreground = "#333333"
    main_font_size = 72
    main_font = ImageFont.truetype(FONT_FACE, main_font_size)
    footer_bbox = (
        MARGIN,
        IMG_HEIGHT - 2 * MARGIN,
        IMG_WIDTH - MARGIN,
        IMG_HEIGHT - MARGIN,
    )
    footer_foreground = "dimgrey"
    footer_font_size = 60
    footer_font = ImageFont.truetype(FONT_FACE, footer_font_size)
    line_spacing = 1.75

    img = Image.new(colour_mode, (IMG_WIDTH, IMG_HEIGHT), background)
    draw = ImageDraw.Draw(img)
    wrapped_main_text = _wrap_text(input.body_text, _get_width(main_bbox), main_font)
    line_height = _get_height(main_font.getbbox("A"))  # type: ignore
    draw.text(  # type: ignore
        xy=(main_bbox[0], main_bbox[1]),
        text=wrapped_main_text,
        fill=main_foreground,
        font=main_font,
        spacing=line_height * (line_spacing - 1),
        # Make the text bold
        stroke_width=1,
        stroke_fill=main_foreground,
    )
    draw.text(  # type: ignore
        xy=(
            footer_bbox[2],
            _get_vertical_center(footer_bbox),
        ),
        text=input.footer_text,
        fill=footer_foreground,
        font=footer_font,
        align="right",
        anchor="rm",
    )

    return SlideOutput(image=img, name=input.name)


def _generate_fullscreen_slide_without_footer(input: SlideInput) -> SlideOutput:
    colour_mode = "L"
    background = "white"
    main_bbox = (MARGIN, MARGIN, IMG_WIDTH - MARGIN, IMG_HEIGHT - MARGIN)
    main_foreground = "#333333"
    main_font_size = 72
    main_font = ImageFont.truetype(FONT_FACE, main_font_size)
    line_spacing = 1.75

    img = Image.new(colour_mode, (IMG_WIDTH, IMG_HEIGHT), background)
    draw = ImageDraw.Draw(img)
    wrapped_main_text = _wrap_text(input.body_text, _get_width(main_bbox), main_font)
    line_height = _get_height(main_font.getbbox("A"))  # type: ignore
    draw.text(  # type: ignore
        xy=(_get_horizontal_center(main_bbox), _get_vertical_center(main_bbox)),
        text=wrapped_main_text,
        fill=main_foreground,
        font=main_font,
        spacing=line_height * (line_spacing - 1),
        align="center",
        anchor="mm",
        # Make the text bold
        stroke_width=1,
        stroke_fill=main_foreground,
    )

    return SlideOutput(image=img, name=input.name)


def _wrap_text(text: str, max_width: int, font: FreeTypeFont) -> str:
    # TODO: replace other whitespace (e.g., tabs) with spaces
    text = text.strip().replace("\r\n", "\n")
    # Keep line breaks that the user manually chose
    lines = [line for line in text.split("\n") if line]
    return "\n".join([_wrap_line(line, max_width, font) for line in lines])


def _wrap_line(line: str, max_width: int, font: FreeTypeFont) -> str:
    words = [w for w in line.split(" ") if w]
    output_lines: List[str] = []
    while words:
        (wrapped_line, words) = _extract_max_prefix(words, max_width, font)
        output_lines.append(wrapped_line)
    return "\n".join(output_lines)


def _extract_max_prefix(
    words: List[str], max_width: int, font: FreeTypeFont
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
        width = _get_width(font.getbbox(longer_output))  # type: ignore
        if width > max_width:
            break
        else:
            output = longer_output
            words = words[1:]
    return (output, words)


def _get_width(bbox: Tuple[int, int, int, int]) -> int:
    left, _, right, _ = bbox
    return right - left


def _get_height(bbox: Tuple[int, int, int, int]) -> int:
    _, top, _, bottom = bbox
    return bottom - top


def _get_horizontal_center(bbox: Tuple[int, int, int, int]) -> float:
    left, _, right, _ = bbox
    return left + (right - left) / 2


def _get_vertical_center(bbox: Tuple[int, int, int, int]) -> float:
    _, top, _, bottom = bbox
    return top + (bottom - top) / 2
