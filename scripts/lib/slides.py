"""
Functions for generating images and translating a message plan on Planning Center Online to a more detailed description of each slide.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Set, Tuple

from autochecklist import Messenger, ProblemLevel
from external_services import BibleVerse, BibleVerseFinder
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

    def _split_message_notes(self, text: str) -> List[str]:
        # The particular value here isn't a big deal, as long as it does not occur within the notes themselves
        slide_boundary = "----- SLIDE BOUNDARY -----"
        slides_prefix_regex = re.compile(
            "^(title )?slides? ?- ?", flags=re.IGNORECASE | re.MULTILINE
        )
        if slides_prefix_regex.match(text):
            delimited_text = slides_prefix_regex.sub(slide_boundary, text)
        else:
            delimited_text = text.replace("\r\n", "\n").replace("\n", slide_boundary)
        notes = delimited_text.split(slide_boundary)
        non_empty_notes = [n.strip() for n in notes if n.strip()]
        return non_empty_notes

    def _split_lyrics(self, text: str) -> List[str]:
        text = text.replace("\r\n", "\n")
        text = re.sub("\n\n+", "\n\n", text)
        text = "\n".join([x for x in text.split("\n") if not x.startswith("#")])
        verses = [v for v in text.split("\n\n") if v]
        return verses

    def _convert_bible_verse_to_blueprint(self, verse: BibleVerse) -> SlideBlueprint:
        verse_text = self._bible_verse_finder.find(verse)
        if verse_text is None:
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"'{verse}' looks like a reference to a Bible verse, but the text could not be found.",
            )
            return SlideBlueprint(
                body_text=str(verse),
                footer_text="",
                name=f"{verse.book} {verse.chapter} {verse.verse} {verse.translation}",
            )
        else:
            return SlideBlueprint(
                body_text=verse_text,
                footer_text=str(verse),
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


FONT_MANAGER = FontManager()


@dataclass
class FontSpec:
    family: List[str]
    style: Literal["normal", "italic", "oblique"]
    max_size: int
    min_size: int

    def make_font(self, size: int) -> FreeTypeFont:
        properties = FontProperties(family=self.family, style=self.style)
        path = FONT_MANAGER.findfont(properties)
        return ImageFont.truetype(path, size=size)


IMG_WIDTH = 1920
IMG_HEIGHT = 1080
OUTER_MARGIN = 100
FONT_FAMILY = ["Helvetica", "Calibri", "sans-serif"]


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


@dataclass
class _Bbox:
    left: int
    top: int
    right: int
    bottom: int

    @staticmethod
    def xywh(x: int, y: int, w: int, h: int) -> _Bbox:
        return _Bbox(left=x, top=y, right=x + w, bottom=y + h)

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
        return [
            (
                self._generate_fullscreen_slide_with_footer(b)
                if b.footer_text
                else self._generate_fullscreen_slide_without_footer(b)
            )
            for b in blueprints
        ]

    def generate_lower_third_slides(
        self, blueprints: List[SlideBlueprint], show_backdrop: bool
    ) -> List[Slide]:
        return [
            (
                self._generate_lower_third_slide_with_footer(b, show_backdrop)
                if b.footer_text
                else self._generate_lower_third_slide_without_footer(b, show_backdrop)
            )
            for b in blueprints
        ]

    def _generate_fullscreen_slide_with_footer(self, input: SlideBlueprint) -> Slide:
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
            font_spec=FontSpec(
                family=FONT_FAMILY, style="normal", min_size=36, max_size=72
            ),
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
            font_spec=FontSpec(
                family=FONT_FAMILY, style="oblique", min_size=30, max_size=60
            ),
            foreground="dimgrey",
            stroke_width=0,
            line_spacing=1.75,
            slide_name=input.name,
        )
        return Slide(image=img, name=input.name)

    def _generate_fullscreen_slide_without_footer(self, input: SlideBlueprint) -> Slide:
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
            font_spec=FontSpec(
                family=FONT_FAMILY, style="normal", min_size=36, max_size=72
            ),
            foreground="#333333",
            stroke_width=1,  # bold
            line_spacing=1.75,
            slide_name=input.name,
        )
        return Slide(image=img, name=input.name)

    def _generate_lower_third_slide_with_footer(
        self, blueprint: SlideBlueprint, show_backdrop: bool
    ) -> Slide:
        img = Image.new(mode="RGBA", size=(IMG_WIDTH, IMG_HEIGHT), color="#00000000")
        draw = ImageDraw.Draw(img)

        if show_backdrop:
            draw.rectangle((0, 825, IMG_WIDTH, 825 + 225), fill="#00000088")
        self._draw_text(
            draw=draw,
            text=blueprint.body_text,
            bbox=_Bbox.xywh(x=25, y=825, w=1870, h=160),
            horiz_align="left",
            vert_align="top",
            font_spec=FontSpec(
                family=FONT_FAMILY, style="normal", min_size=24, max_size=48
            ),
            foreground="white",
            stroke_width=1,
            line_spacing=1.5,
            slide_name=blueprint.name,
        )
        self._draw_text(
            draw=draw,
            text=blueprint.footer_text,
            bbox=_Bbox.xywh(x=25, y=985, w=1870, h=50),
            horiz_align="right",
            vert_align="center",
            font_spec=FontSpec(
                family=FONT_FAMILY, style="oblique", min_size=20, max_size=40
            ),
            foreground="#DDDDDD",
            stroke_width=0,
            line_spacing=1,
            slide_name=blueprint.name,
        )

        return Slide(image=img, name=blueprint.name)

    def _generate_lower_third_slide_without_footer(
        self, blueprint: SlideBlueprint, show_backdrop: bool
    ) -> Slide:
        img = Image.new(mode="RGBA", size=(IMG_WIDTH, IMG_HEIGHT), color="#00000000")
        draw = ImageDraw.Draw(img)

        if show_backdrop:
            draw.rectangle((0, 850, IMG_WIDTH, 850 + 200), fill="#00000088")

        self._draw_text(
            draw=draw,
            text=blueprint.body_text,
            bbox=_Bbox.xywh(x=25, y=850, w=1870, h=200),
            horiz_align="center",
            vert_align="center",
            font_spec=FontSpec(
                family=FONT_FAMILY, style="normal", min_size=24, max_size=48
            ),
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
        font_spec: FontSpec,
        foreground: str,
        stroke_width: int,
        line_spacing: float,
        slide_name: str,
    ):
        size = font_spec.max_size
        while True:
            font = font_spec.make_font(size)
            wrapped_text = _wrap_text(text, bbox.get_width(), font, stroke_width)

            anchor_horiz = {"left": "l", "center": "m", "right": "r"}[horiz_align]
            anchor_vert = {"top": "a", "center": "m", "bottom": "d"}[vert_align]
            anchor = f"{anchor_horiz}{anchor_vert}"

            x = {
                "left": bbox.left,
                "center": bbox.get_horizontal_centre(),
                "right": bbox.right,
            }[horiz_align]
            y = {
                "top": bbox.top,
                "center": bbox.get_vertical_centre(),
                "bottom": bbox.bottom,
            }[vert_align]
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
            text_overflowed = (
                textbbox.get_height() > bbox.get_height()
                or textbbox.get_width() > bbox.get_width()
            )
            if text_overflowed and size <= font_spec.min_size:
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
    return _Bbox(*font.getbbox(text, stroke_width=stroke_width))
