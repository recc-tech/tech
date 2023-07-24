import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from autochecklist import Messenger, ProblemLevel
from slides.generate import SlideBlueprint

SAFE_FILENAME_CHARACTERS = re.compile("^[a-z0-9-_ &,]$", re.IGNORECASE)
# The maximum length of the full path to a file on Windows is 260 (see
# https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry)
# In practice, it should be safe to save files with a length of 50; we won't
# put the slides in directories whose length exceeds 200 characters.
# TODO: warn the user if the output directory is too long.
MAX_FILENAME_LEN = 50


class SlideBlueprintReader:
    def __init__(self, messenger: Messenger):
        self._messenger = messenger

    def load_message_notes(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r", encoding="utf-8") as f:
            text = f.read()
        # The particular value here isn't a big deal, as long as it does not occur within the notes themselves
        slide_boundary = "----- SLIDE BOUNDARY -----"
        text = re.sub(
            "^(title )?slides? ?- ?",
            slide_boundary,
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        slide_contents = text.split(slide_boundary)[1:]
        slide_contents = [s.strip() for s in slide_contents if s.strip()]
        return [_convert_note_to_blueprint(s) for s in slide_contents]

    def load_lyrics(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r", encoding="utf-8") as f:
            text = f.read()

        # Don't show lyrics from different verses on the same slide
        text = text.replace("\r\n", "\n")
        text = re.sub("\n\n+", "\n\n", text)
        verses = [v for v in text.split("\n\n") if v]

        blueprints: List[SlideBlueprint] = []
        for v in verses:
            blueprints += _convert_verse_to_blueprints(v)
        return blueprints

    def load_json(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r", encoding="utf-8") as f:
            json_obj = json.load(f)
        try:
            return _parse_json_obj(json_obj)
        except Exception as e:
            self._messenger.log_problem(
                ProblemLevel.FATAL,
                f"An error occurred while loading the previous data: {e}",
            )
            sys.exit(1)

    def save_json(self, file: Path, slides: List[SlideBlueprint]):
        slides_dicts = [s.__dict__ for s in slides]
        with open(file, mode="w", encoding="utf-8") as f:
            json.dump({"slides": slides_dicts}, f, indent="\t")


def _convert_note_to_blueprint(note: str) -> SlideBlueprint:
    # TODO: recognize and look up Bible verses
    return SlideBlueprint(
        body_text=note, footer_text="", name=_convert_text_to_filename(note)
    )


def _convert_verse_to_blueprints(verse: str) -> List[SlideBlueprint]:
    # TODO: Split the verse if it's too long. A simple solution would be to go by number of lines, but really we would need to call the SlideGenerator somehow to check how much text can fit
    # TODO: Recognize repeated lyrics and replace them with <VERSE> (x<NUM-REPETITIONS>)?
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
