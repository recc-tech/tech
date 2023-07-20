import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

from autochecklist import Messenger, ProblemLevel
from slides.generate import SlideBlueprint


class SlideBlueprintReader:
    def __init__(self, messenger: Messenger):
        self._messenger = messenger

    def load_message_notes(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r") as f:
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
        return [self._convert_note_to_blueprint(s) for s in slide_contents]

    def load_lyrics(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r") as f:
            text = f.read()

        # Don't show lyrics from different verses on the same slide
        text = text.replace("\r\n", "\n")
        text = re.sub("\n\n+", "\n\n", text)
        verses = [v for v in text.split("\n\n") if v]

        blueprints: List[SlideBlueprint] = []
        for v in verses:
            blueprints += self._convert_verse_to_blueprints(v)
        return blueprints

    def load_json(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r") as f:
            json_obj = json.load(f)
        try:
            return self._parse_json_obj(json_obj)
        except Exception as e:
            self._messenger.log_problem(
                ProblemLevel.FATAL,
                f"An error occurred while loading the previous data: {e}",
            )
            sys.exit(1)

    def save_json(self, file: Path, slides: List[SlideBlueprint]):
        slides_dicts = [s.__dict__ for s in slides]
        with open(file, mode="w") as f:
            json.dump({"slides": slides_dicts}, f, indent="\t")

    def _convert_note_to_blueprint(self, note: str) -> SlideBlueprint:
        # TODO: recognize and look up Bible verses
        return SlideBlueprint(body=note, footer="", name="", generate_name=True)

    def _convert_verse_to_blueprints(self, verse: str) -> List[SlideBlueprint]:
        # TODO: Split the verse if it's too long. A simple solution would be to go by number of lines, but really we would need to call the SlideGenerator somehow to check how much text can fit
        # TODO: Recognize repeated lyrics and replace them with <VERSE> (x<NUM-REPETITIONS>)?
        return [SlideBlueprint(body=verse, footer="", name="", generate_name=True)]

    def _parse_json_obj(
        self, json_obj: Dict[str, List[Dict[str, Any]]]
    ) -> List[SlideBlueprint]:
        json_slides = json_obj["slides"]

        unrecognized_properties = [x for x in json_obj.keys() if x != "slides"]
        prop = "property" if len(unrecognized_properties) == 1 else "properties"
        if unrecognized_properties:
            raise ValueError(
                f"Unrecognized {prop}: {', '.join(unrecognized_properties)}."
            )

        blueprints = [
            self._parse_json_slide(js, i) for (i, js) in enumerate(json_slides)
        ]
        self._validate_slide_blueprints(blueprints)
        return blueprints

    def _parse_json_slide(
        self, json_slide: Dict[str, Any], index: int
    ) -> SlideBlueprint:
        body_text = json_slide["body_text"]
        footer_text = json_slide["footer_text"]
        name = json_slide["name"]

        unrecognized_properties = [
            x
            for x in json_slide.keys()
            if x not in ["body_text", "footer_text", "name"]
        ]
        if unrecognized_properties:
            prop = "property" if len(unrecognized_properties) == 1 else "properties"
            raise ValueError(
                f'Unrecognized {prop} in "slides"[{index}]: {", ".join(unrecognized_properties)}.'
            )

        return SlideBlueprint(body_text, footer_text, name)

    def _validate_slide_blueprints(self, blueprints: List[SlideBlueprint]):
        has_errors = False

        names = sorted(
            [Path(b.name).with_suffix("").as_posix().lower() for b in blueprints]
        )
        repeated_names: Set[str] = set()
        valid_filename_regex = re.compile("^[a-z0-9 _-]+$")
        for i, name in enumerate(names):
            if name in repeated_names:
                continue
            if i + 1 < len(names) and name == names[i + 1]:
                repeated_names.add(name)
                has_errors = True
                self._messenger.log_problem(
                    ProblemLevel.FATAL,
                    f'The name "{name.lower()}" is given to more than one slide. Note that filenames are case-insensitive on Windows and that this script saves all files with a .png extension.',
                )
            if len(name) == 0:
                has_errors = True
                self._messenger.log_problem(
                    ProblemLevel.FATAL, "Missing name for a slide."
                )
            if not valid_filename_regex.match(name):
                has_errors = True
                self._messenger.log_problem(
                    ProblemLevel.FATAL,
                    f'Filename "{name}" contains forbidden characters. The filename should match the regular expression "{valid_filename_regex.pattern}".',
                )

        if has_errors:
            raise ValueError("Could not load previous data.")
