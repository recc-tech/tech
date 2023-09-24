from __future__ import annotations

import json
import re
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote_plus

from autochecklist import CancellationToken, Messenger, ProblemLevel
from common import ReccWebDriver
from selenium.common.exceptions import NoSuchElementException
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
    def parse(text: str) -> Optional[Tuple[List[BibleVerse], str]]:
        try:
            books_regex = r"(Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|1 Samuel|2 Samuel|1 Kings|2 Kings|1 Chronicles|2 Chronicles|Ezra|Nehemiah|Esther|Job|Psalm|Psalms|Proverbs|Ecclesiastes|Song of Solomon|Song of Songs|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Marc|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation|Revelations)"
            chapter_regex = r"(\d\d?\d?)"
            verse_range_regex = r"(?:\d{1,3}(?:-\d{1,3})?)"
            verses_regex = f"({verse_range_regex}(?:,{verse_range_regex})*)"
            # All the translations available on BibleGateway as of 2023-09-17
            translations = "KJ21|ASV|AMP|AMPC|BRG|CSB|CEB|CJB|CEV|DARBY|DLNT|DRA|ERV|EHV|ESV|ESVUK|EXB|GNV|GW|GNT|HCSB|ICB|ISV|PHILLIPS|JUB|KJV|AKJV|LSB|LEB|TLB|MSG|MEV|MOUNCE|NOG|NABRE|NASB|NASB1995|NCB|NCV|NET|NIRV|NIV|NIVUK|NKJV|NLV|NLT|NMB|NRSVA|NRSVACE|NRSVCE|NRSVUE|NTE|OJB|RGT|RSV|RSVCE|TLV|VOICE|WEB|WE|WYC|YLT"
            translation_regex = r"(?: \(?(" + translations + r")\)?)?"
            verse_regex = re.compile(
                f"{books_regex} {chapter_regex}:{verses_regex}{translation_regex}(.*)",
                re.IGNORECASE,
            )

            m = verse_regex.fullmatch(text.strip())
            if m is None:
                return None

            book = BibleVerse._parse_book(m.group(1))
            chapter = int(m.group(2))
            verses = BibleVerse._parse_verses(m.group(3))
            translation = "NLT" if m.group(4) is None else m.group(4).upper()
            remaining_text = m.group(5)
            return (
                [BibleVerse(book, chapter, v, translation) for v in verses],
                remaining_text,
            )
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
    def __init__(
        self,
        driver: ReccWebDriver,
        messenger: Messenger,
        cancellation_token: Optional[CancellationToken],
    ):
        self._driver = driver
        self._messenger = messenger

        try:
            self._set_page_options(cancellation_token)
        except Exception:
            self._messenger.log_problem(
                ProblemLevel.WARN,
                f"Failed to set page options on BibleGateway. Some verses might contain extra unwanted text, such as footnote numbers or cross-references.",
                stacktrace=traceback.format_exc(),
            )

    def find(self, verse: BibleVerse) -> Optional[str]:
        try:
            self._get_page(verse)
            by = By.XPATH
            xpath = "//div[@class='passage-text']//p"
            paragraphs = self._driver.find_elements(by, xpath)
            if not paragraphs:
                raise NoSuchElementException(
                    f"No elements found for the given criteria (by = {by}, value = '{xpath}')."
                )
            text = "\n".join([p.get_attribute("innerText") for p in paragraphs])  # type: ignore
            return self._normalize(text)
        except Exception:
            self._messenger.log_problem(
                ProblemLevel.WARN,
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

    def _set_page_options(self, cancellation_token: Optional[CancellationToken]):
        self._get_page(BibleVerse("Genesis", 1, 1, "NLT"), use_print_interface=False)

        page_options_btn = self._driver.wait_for_single_element(
            By.XPATH,
            "//*[name()='svg']/*[name()='title'][contains(., 'Page Options')]/..",
            cancellation_token=cancellation_token,
        )
        page_options_btn.click()

        for title in ["Cross-references", "Footnotes", "Verse Numbers", "Headings"]:
            checkbox = self._driver.wait_for_single_element(
                By.XPATH,
                f"//*[name()='svg']/*[name()='title'][contains(., '{title}')]/..",
                cancellation_token=cancellation_token,
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
                    f"While setting page options on BibleGateway, could not determine whether option '{title}' is enabled or disabled. Some verses might contain extra unwanted text, such as footnote numbers or cross-references.",
                )

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text)


class SlideBlueprintReader:
    def __init__(self, messenger: Messenger, bible_verse_finder: BibleVerseFinder):
        self._messenger = messenger
        self._bible_verse_finder = bible_verse_finder

    def load_message_notes(self, file: Path) -> List[SlideBlueprint]:
        # TODO: Test this with the 2023-09-24 notes; they didn't work great
        with open(file, mode="r", encoding="utf-8") as f:
            text = f.read()

        # The "Slide-" prefix is not used consistently, so just get rid of it
        text = re.sub(
            "^(title )?slides? ?- ?", "", text, flags=re.IGNORECASE | re.MULTILINE
        )
        text = text.replace("\r\n", "\n")
        blueprints: List[SlideBlueprint] = []
        while text:
            lines = [x.strip() for x in text.split("\n")]
            non_empty_lines = [x for x in lines if x]
            if not non_empty_lines:
                break
            # TODO: This raised an IndexError. Test it better?
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
                # Remove redundant text
                verse_regexes = [
                    f'(?:{v.verse})? ?(\\"|“|”)?{re.escape(b.body_text)}(\\"|“|”)?'
                    for (v, b) in blueprint_by_verse.items()
                ]
                full_passage_regex = (
                    r"\s+".join(verse_regexes).replace("\\ ", " ")
                    # Allow line breaks between any words. While we're at it,
                    # allow any other weird whitespace (double spaces, etc.)
                    # too
                    .replace(" ", r"(?:\s+)")
                )
                text = re.sub(full_passage_regex, "", text)
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
    # TODO: Split the verse if it's too long. A simple solution would be to go by number of lines, but really we would need to call the SlideGenerator somehow to check how much text can fit
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
