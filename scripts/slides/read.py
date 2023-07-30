from __future__ import annotations

import json
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from autochecklist import Messenger, ProblemLevel
from common import ReccWebDriver
from selenium.webdriver.common.by import By
from slides.generate import SlideBlueprint

SAFE_FILENAME_CHARACTERS = re.compile("^[a-z0-9-_ &,]$", re.IGNORECASE)
# The maximum length of the full path to a file on Windows is 260 (see
# https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry)
# In practice, it should be safe to save files with a length of 50; we won't
# put the slides in directories whose length exceeds 200 characters.
# TODO: warn the user if the output directory is too long.
MAX_FILENAME_LEN = 50


@dataclass(frozen=True)
class BibleVerse:
    book: str
    chapter: int
    verse: int
    translation: str

    def __str__(self) -> str:
        return f"{self.book} {self.chapter}:{self.verse} ({self.translation})"

    @staticmethod
    def parse(text: str) -> Optional[List[BibleVerse]]:
        try:
            books_regex = r"(Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|1 Samuel|2 Samuel|1 Kings|2 Kings|1 Chronicles|2 Chronicles|Ezra|Nehemiah|Esther|Job|Psalm|Psalms|Proverbs|Ecclesiastes|Song of Solomon|Song of Songs|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Marc|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation|Revelations)"
            chapter_regex = r"(\d\d?\d?)"
            verse_range_regex = r"(?:\d{1,3}(?:-\d{1,3})?)"
            verses_regex = f"({verse_range_regex}(?:,{verse_range_regex})*)"
            translation_regex = r"(?: \(?([A-Z0-9]{2,8})\)?)?"
            verse_regex = re.compile(
                f"{books_regex} {chapter_regex}:{verses_regex}{translation_regex}",
                re.IGNORECASE,
            )

            m = verse_regex.fullmatch(text.strip())
            if m is None:
                return None

            book = BibleVerse._parse_book(m.group(1))
            chapter = int(m.group(2))
            verses = BibleVerse._parse_verses(m.group(3))
            translation = "NLT" if m.group(4) is None else m.group(4).upper()
            return [BibleVerse(book, chapter, v, translation) for v in verses]
        except Exception:
            return None

    @staticmethod
    def _parse_book(book: str) -> str:
        if book == "Psalms":
            book = "Psalm"
        elif book == "Song of Songs":
            book = "Song of Solomon"
        elif book == "Marc":
            book = "Mark"
        elif book == "Revelations":
            book = "Revelation"
        return book

    @staticmethod
    def _parse_verses(raw_verses: str) -> List[int]:
        verse_ranges = raw_verses.split(",")
        split_verse_ranges = [
            tuple(map(int, v.split("-"))) if "-" in v else (int(v), int(v))
            for v in verse_ranges
        ]
        verse_sets = [list(range(x[0], x[1] + 1)) for x in split_verse_ranges]
        flattened_verse_set = [v for vs in verse_sets for v in vs]
        return flattened_verse_set


class BibleVerseFinder:
    def __init__(self, driver: ReccWebDriver, messenger: Messenger):
        self._driver = driver
        self._messenger = messenger

        try:
            self._set_page_options()
        except Exception:
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"Failed to set page options on BibleGateway.",
                stacktrace=traceback.format_exc(),
            )

    def find(self, verse: BibleVerse) -> Optional[str]:
        try:
            self._get_page(verse)
            paragraphs = self._driver.find_elements(
                By.XPATH, "//div[@class='passage-text']//p"
            )
            text = "\n".join([p.get_attribute("innerText") for p in paragraphs])  # type: ignore
            return self._normalize(text)
        except Exception:
            self._messenger.log_problem(
                ProblemLevel.ERROR,
                f"Failed to fetch text for Bible verse {verse}.",
                stacktrace=traceback.format_exc(),
            )
            return None

    def _get_page(self, verse: BibleVerse, use_print_interface: bool = True):
        search = quote_plus(f"{verse.book} {verse.chapter}:{verse.verse}")
        url = f"https://www.biblegateway.com/passage/?search={search}&version={verse.translation}"
        if use_print_interface:
            url += "&interface=print"
        self._driver.get(url)

    def _set_page_options(self):
        self._get_page(BibleVerse("Genesis", 1, 1, "NLT"), use_print_interface=False)

        page_options_btn = self._driver.wait_for_single_element(
            By.XPATH,
            "//*[name()='svg']/*[name()='title'][contains(., 'Page Options')]/..",
        )
        page_options_btn.click()

        for title in ["Cross-references", "Footnotes", "Verse Numbers", "Headings"]:
            checkbox = self._driver.wait_for_single_element(
                By.XPATH,
                f"//*[name()='svg']/*[name()='title'][contains(., '{title}')]/..",
            )
            checkbox_name = checkbox.get_attribute("name")  # type: ignore
            if checkbox_name == "checked":
                self._messenger.log_debug(
                    f"Checkbox for option '{title}' was checked. Disabling it now."
                )
                checkbox.click()
            elif checkbox_name == "square":
                self._messenger.log_debug(
                    f"Checkbox for option '{title}' was already unchecked."
                )
            else:
                self._messenger.log_problem(
                    ProblemLevel.WARN,
                    f"Could not determine whether option '{title}' is enabled or disabled.",
                )

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text)


class SlideBlueprintReader:
    def __init__(self, messenger: Messenger, bible_verse_finder: BibleVerseFinder):
        self._messenger = messenger
        self._bible_verse_finder = bible_verse_finder

    def load_message_notes(self, file: Path) -> List[SlideBlueprint]:
        with open(file, mode="r", encoding="utf-8") as f:
            text = f.read()

        slide_contents = self._split_message_notes(text)

        blueprints: List[SlideBlueprint] = []
        for s in slide_contents:
            blueprints += self._convert_note_to_blueprint(s)
        return blueprints

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
            self._messenger.log_problem(
                ProblemLevel.FATAL,
                f"An error occurred while loading the previous data: {e}",
            )
            sys.exit(1)

    def save_json(self, file: Path, slides: List[SlideBlueprint]):
        slides_dicts = [s.__dict__ for s in slides]
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

    def _convert_note_to_blueprint(self, note: str) -> List[SlideBlueprint]:
        bible_verses = BibleVerse.parse(note)
        if bible_verses is None:
            return [
                SlideBlueprint(
                    body_text=note, footer_text="", name=_convert_text_to_filename(note)
                )
            ]
        else:
            blueprints: List[SlideBlueprint] = []
            for v in bible_verses:
                verse_blueprint = self._convert_bible_verse_to_blueprint(v)
                if verse_blueprint is None:
                    default_blueprint = SlideBlueprint(
                        body_text=str(v),
                        footer_text="",
                        name=f"{v.book} {v.chapter} {v.verse} {v.translation}",
                    )
                    blueprints.append(default_blueprint)
                else:
                    blueprints.append(verse_blueprint)
            return blueprints

    def _convert_bible_verse_to_blueprint(
        self, verse: BibleVerse
    ) -> Optional[SlideBlueprint]:
        verse_text = self._bible_verse_finder.find(verse)
        if verse_text is None:
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"'{verse}' looks like a reference to a Bible verse, but the text could not be found.",
            )
            return None
        else:
            return SlideBlueprint(
                body_text=verse_text,
                footer_text=str(verse),
                name=f"{verse.book} {verse.chapter} {verse.verse} {verse.translation}",
            )


def _convert_song_verse_to_blueprints(verse: str) -> List[SlideBlueprint]:
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
