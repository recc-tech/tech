"""
Functions for generating images and translating a message plan on Planning Center Online to a more detailed description of each slide.
"""

from __future__ import annotations

import json
import re
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from autochecklist import Messenger, ProblemLevel
from config import (
    Bbox,
    Config,
    Font,
    FooterSlideStyle,
    NoFooterSlideStyle,
    Rectangle,
    Textbox,
)
from external_services.bible import BibleVerse, BibleVerseFinder
from matplotlib.font_manager import FontManager, FontProperties
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

SAFE_FILENAME_CHARACTERS = re.compile("^[a-z0-9-_ &,]$", re.IGNORECASE)
# The maximum length of the full path to a file on Windows is 260 (see
# https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry)
# In practice, it should be safe to save files with a length of 50; we won't
# put the slides in directories whose length exceeds 200 characters.
MAX_FILENAME_LEN = 50


class SlideBlueprintReader:
    def __init__(self, messenger: Messenger, bible_verse_finder: BibleVerseFinder):
        self._messenger = messenger
        self._bible_verse_finder = bible_verse_finder

    def load_message_notes(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r", encoding="utf-8") as f:
            text = f.read()

        # Prefixes like "-", "Slide-", and "Title Slide -" are not used
        # consistently, so just get rid of them
        text = re.sub(
            r"^((title )?slides?)?\s*-\s*", "", text, flags=re.IGNORECASE | re.MULTILINE
        )
        text = text.replace("\r\n", "\n")
        blueprints: List[SlideBlueprint] = []
        while text:
            lines = [x.strip() for x in text.split("\n")]
            non_empty_lines = [x for x in lines if x]
            if not non_empty_lines:
                break
            first_line, remaining_lines = non_empty_lines[0], non_empty_lines[1:]
            text = "\n".join(remaining_lines)
            parsed_line = BibleVerse.parse(first_line)
            if parsed_line is None:
                blueprints.append(
                    SlideBlueprint(
                        body_text=first_line,
                        footer_text="",
                        name=_convert_text_to_filename(first_line),
                    )
                )
            else:
                (verses, remaining_line) = parsed_line
                if remaining_line:
                    text = f"{remaining_line}\n{text}"
                blueprint_by_verse = {
                    v: self._convert_bible_verse_to_blueprint(v) for v in verses
                }
                blueprints += blueprint_by_verse.values()
                # Remove redundant text (e.g., verse text following verse
                # reference)
                for v, b in blueprint_by_verse.items():
                    # Trailing punctuation is often omitted or changed
                    has_trailing_punctuation = b.body_text[-1] in [",", "."]
                    body_regex = (
                        re.escape(b.body_text[:-1]) + r"(\.|,)?"
                        if has_trailing_punctuation
                        else re.escape(b.body_text)
                    )
                    regex = f'(?:{v.verse})? ?(\\"|“|”)?{body_regex}(\\"|“|”)?'.replace(
                        r"\ ", " "
                    ).replace(" ", r"(?:\s+)")
                    text = re.sub(regex, "", text)
        # Duplicate slides suggest there may be a typo in the message notes
        # In any case, there's no need to generate a slide multiple times
        firsts: Set[SlideBlueprint] = set()
        unique_blueprints_in_order: List[SlideBlueprint] = []
        for b in blueprints:
            if b in firsts:
                self._messenger.log_problem(
                    level=ProblemLevel.WARN,
                    message=f'The message notes ask for multiple slides with body "{b.body_text}", name "{b.name}", and footer "{b.footer_text}". Is there a typo?',
                )
            else:
                firsts.add(b)
                unique_blueprints_in_order.append(b)
        return unique_blueprints_in_order

    def load_lyrics(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r", encoding="utf-8") as f:
            text = f.read()

        verses = self._split_lyrics(text)

        blueprints: List[SlideBlueprint] = []
        for v in verses:
            blueprints += _convert_song_verse_to_blueprints(v)
        return blueprints

    def load_json(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r", encoding="utf-8") as f:
            json_obj = json.load(f)
        try:
            return _parse_json_obj(json_obj)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load the previous slides from '{file}'."
            ) from e

    def save_json(self, file: Path, slides: List[SlideBlueprint]):
        slides_dicts = [s.__dict__ for s in slides]
        file.parent.mkdir(exist_ok=True, parents=True)
        with open(file, mode="w", encoding="utf-8") as f:
            json.dump({"slides": slides_dicts}, f, indent="\t")

    def _split_lyrics(self, text: str) -> List[str]:
        text = text.replace("\r\n", "\n")
        text = re.sub("\n\n+", "\n\n", text)
        text = "\n".join([x for x in text.split("\n") if not x.startswith("#")])
        verses = [v for v in text.split("\n\n") if v]
        return verses

    def _convert_bible_verse_to_blueprint(self, verse: BibleVerse) -> SlideBlueprint:
        try:
            verse_text = self._bible_verse_finder.find(verse)
            return SlideBlueprint(
                body_text=verse_text,
                footer_text=str(verse),
                name=f"{verse.book} {verse.chapter} {verse.verse} {verse.translation}",
            )
        except Exception:
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"'{verse}' looks like a reference to a Bible verse, but the text could not be found.",
                stacktrace=traceback.format_exc(),
            )
            return SlideBlueprint(
                body_text=str(verse),
                footer_text="",
                name=f"{verse.book} {verse.chapter} {verse.verse} {verse.translation}",
            )


def _convert_song_verse_to_blueprints(verse: str) -> List[SlideBlueprint]:
    return [SlideBlueprint(body_text=verse, footer_text="", name="")]


def _parse_json_obj(json_obj: Dict[str, List[Dict[str, Any]]]) -> List[SlideBlueprint]:
    json_slides = json_obj["slides"]

    unrecognized_properties = [x for x in json_obj.keys() if x != "slides"]
    prop = "property" if len(unrecognized_properties) == 1 else "properties"
    if unrecognized_properties:
        raise ValueError(f"Unrecognized {prop}: {', '.join(unrecognized_properties)}.")

    return [_parse_json_slide(js, i) for (i, js) in enumerate(json_slides)]


def _parse_json_slide(json_slide: Dict[str, Any], index: int) -> SlideBlueprint:
    body_text = json_slide["body_text"]
    footer_text = json_slide["footer_text"]
    name = json_slide["name"]

    unrecognized_properties = [
        x for x in json_slide.keys() if x not in ["body_text", "footer_text", "name"]
    ]
    if unrecognized_properties:
        prop = "property" if len(unrecognized_properties) == 1 else "properties"
        raise ValueError(
            f'Unrecognized {prop} in "slides"[{index}]: {", ".join(unrecognized_properties)}.'
        )

    return SlideBlueprint(body_text, footer_text, name)


def _convert_text_to_filename(text: str) -> str:
    ascii_text = "".join(
        [c if SAFE_FILENAME_CHARACTERS.match(c) else "_" for c in text]
    )
    if len(ascii_text) <= MAX_FILENAME_LEN:
        return ascii_text
    else:
        words = [w for w in ascii_text.split(" ") if w]
        filename = words[0]
        words = words[1:]
        for w in words:
            longer_filename = f"{filename} {w}"
            if len(longer_filename) > MAX_FILENAME_LEN:
                break
            else:
                filename = longer_filename
        return filename[0:MAX_FILENAME_LEN]


@dataclass(frozen=True)
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


class SlideGenerator:
    def __init__(self, messenger: Messenger, config: Config):
        self._messenger = messenger
        self._config = config
        self._font_manager = FontManager()

    def generate_fullscreen_slides(
        self, blueprints: List[SlideBlueprint]
    ) -> List[Slide]:
        return [
            (
                self._generate_slide_with_footer(
                    b, self._config.fullscreen_scripture_style
                )
                if b.footer_text
                else self._generate_slide_without_footer(
                    b, self._config.fullscreen_message_style
                )
            )
            for b in blueprints
        ]

    def generate_lower_third_slides(
        self, blueprints: List[SlideBlueprint]
    ) -> List[Slide]:
        return [
            (
                self._generate_slide_with_footer(
                    b, self._config.lowerthird_scripture_style
                )
                if b.footer_text
                else self._generate_slide_without_footer(
                    b, self._config.lowerthird_message_style
                )
            )
            for b in blueprints
        ]

    def _generate_slide_without_footer(
        self, blueprint: SlideBlueprint, style: NoFooterSlideStyle
    ) -> Slide:
        img = Image.new(
            mode=style.mode,
            size=style.width_height,
            color=str(style.background_colour),
        )
        draw = ImageDraw.Draw(img)
        for rect in style.shapes:
            self._draw_rectangle(draw, rect)
        self._draw_text(
            draw=draw,
            text=blueprint.body_text,
            slide_name=blueprint.name,
            textbox=style.body,
        )
        return Slide(image=img, name=blueprint.name)

    def _generate_slide_with_footer(
        self, blueprint: SlideBlueprint, style: FooterSlideStyle
    ) -> Slide:
        img = Image.new(
            mode=style.mode,
            size=style.width_height,
            color=str(style.background_colour),
        )
        draw = ImageDraw.Draw(img)
        for rect in style.shapes:
            self._draw_rectangle(draw, rect)
        self._draw_text(
            draw=draw,
            text=blueprint.body_text,
            slide_name=blueprint.name,
            textbox=style.body,
        )
        self._draw_text(
            draw=draw,
            text=blueprint.footer_text,
            slide_name=blueprint.name,
            textbox=style.footer,
        )
        return Slide(image=img, name=blueprint.name)

    def _draw_text(
        self, draw: ImageDraw.ImageDraw, text: str, slide_name: str, textbox: Textbox
    ):
        size = textbox.font.max_size
        bbox = textbox.bbox
        halign = textbox.horiz_align
        valign = textbox.vert_align
        while True:
            font = self.make_font(textbox.font, size)
            wrapped_text = _wrap_text(
                text, bbox.get_width(), font, textbox.stroke_width
            )

            anchor_horiz = {"left": "l", "center": "m", "right": "r"}[halign]
            anchor_vert = {"top": "a", "center": "m", "bottom": "d"}[valign]
            anchor = f"{anchor_horiz}{anchor_vert}"

            x = {
                "left": bbox.left,
                "center": bbox.get_horizontal_centre(),
                "right": bbox.right,
            }[halign]
            y = {
                "top": bbox.top,
                "center": bbox.get_vertical_centre(),
                "bottom": bbox.bottom,
            }[valign]
            xy = (x, y)

            line_height = _get_font_bbox("A", font, textbox.stroke_width).get_height()
            textbbox = Bbox(
                *draw.textbbox(
                    xy=xy,
                    text=wrapped_text,
                    font=font,
                    spacing=int(line_height * (textbox.line_spacing - 1)),
                    align=textbox.horiz_align,
                    anchor=anchor,
                    stroke_width=textbox.stroke_width,
                )
            )
            text_overflowed = (
                textbbox.get_height() > bbox.get_height()
                or textbbox.get_width() > bbox.get_width()
            )
            if text_overflowed and size <= textbox.font.min_size:
                self._messenger.log_problem(
                    ProblemLevel.WARN,
                    f"The text in slide '{slide_name}' does not fit within the normal text box, even with the smallest font size.",
                )
                break
            elif text_overflowed:
                size -= 1
                continue
            else:
                # Text fits :)
                break
        draw.text(
            xy=xy,
            text=wrapped_text,
            fill=str(textbox.text_colour),
            font=font,
            spacing=int(line_height * (textbox.line_spacing - 1)),
            align=halign,
            anchor=anchor,
            stroke_width=textbox.stroke_width,
            stroke_fill=str(textbox.text_colour),
        )

    def _draw_rectangle(self, draw: ImageDraw.ImageDraw, rect: Rectangle) -> None:
        b = rect.bbox
        draw.rectangle(
            xy=(b.left, b.top, b.right, b.bottom),
            fill=str(rect.background_colour),
        )

    def make_font(self, font: Font, size: int) -> FreeTypeFont:
        properties = FontProperties(family=font.family, style=font.style)
        path = self._font_manager.findfont(properties)
        return ImageFont.truetype(path, size=size)


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


def _get_font_bbox(text: str, font: FreeTypeFont, stroke_width: int) -> Bbox:
    left, top, right, bottom = font.getbbox(text, stroke_width=stroke_width)
    return Bbox(left=int(left), top=int(top), right=int(right), bottom=int(bottom))
