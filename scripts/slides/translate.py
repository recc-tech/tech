import json
import re
from pathlib import Path
from typing import Any, Dict, List

from slides.generate import SlideInput


def load_txt(file: Path) -> List[str]:
    with open(file, mode="r") as f:
        lines = f.readlines()
    return [_remove_prefix(line) for line in lines]


def load_json(file: Path) -> List[SlideInput]:
    with open(file, mode="r") as f:
        json_obj = json.load(f)
    return _parse_json_obj(json_obj)


def save_json(file: Path, slides: List[SlideInput]):
    slides_dicts = [s.__dict__ for s in slides]
    with open(file, mode="w") as f:
        json.dump({"slides": slides_dicts}, f, indent="\t")


def parse_slides(lines: List[str]) -> List[SlideInput]:
    return [_convert_line_to_slide_contents(line) for line in lines]


def _remove_prefix(line: str) -> str:
    line = line.strip()
    line = re.sub("^(title )?slides? ?- ?", "", line, flags=re.IGNORECASE)
    return line


def _parse_json_obj(json_obj: Dict[str, List[Dict[str, Any]]]) -> List[SlideInput]:
    json_slides = json_obj["slides"]

    unrecognized_properties = [x for x in json_obj.keys() if x != "slides"]
    prop = "property" if len(unrecognized_properties) == 1 else "properties"
    if unrecognized_properties:
        raise ValueError(f"Unrecognized {prop}: {', '.join(unrecognized_properties)}.")

    return [_parse_json_slide(js, i) for (i, js) in enumerate(json_slides)]


def _parse_json_slide(json_slide: Dict[str, Any], index: int) -> SlideInput:
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

    return SlideInput(body_text, footer_text, name)


def _convert_line_to_slide_contents(line: str) -> SlideInput:
    # TODO: recognize and look up Bible verses
    # TODO: look up song lyrics? CCLI, or only text lyrics?
    return SlideInput(body_text=line, footer_text="", name="")
