"""
Functions for generating images and translating a message plan on Planning Center Online to a more detailed description of each slide.
"""

from __future__ import annotations

import json
import re
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple
from urllib.parse import quote_plus

from autochecklist import CancellationToken, Messenger, ProblemLevel
from matplotlib.font_manager import FontManager, FontProperties
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from .web_driver import ReccWebDriver


def make_font(
    family: List[str],
    style: Literal["normal", "italic", "oblique"],
    size: int,
    manager: FontManager,
) -> FreeTypeFont:
    properties = FontProperties(family=family, style=style)
    path = manager.findfont(properties)
    return ImageFont.truetype(path, size=size)


SAFE_FILENAME_CHARACTERS = re.compile("^[a-z0-9-_ &,]$", re.IGNORECASE)
# The maximum length of the full path to a file on Windows is 260 (see
# https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry)
# In practice, it should be safe to save files with a length of 50; we won't
# put the slides in directories whose length exceeds 200 characters.
MAX_FILENAME_LEN = 50


# region Create list of Bible book names and aliases

_canonical_book_name_dict = {
    "genesis": "Genesis",
    "gen": "Genesis",
    "ge": "Genesis",
    "gn": "Genesis",
    "exodus": "Exodus",
    "ex": "Exodus",
    "exod": "Exodus",
    "exo": "Exodus",
    "leviticus": "Leviticus",
    "lev": "Leviticus",
    "le": "Leviticus",
    "lv": "Leviticus",
    "numbers": "Numbers",
    "num": "Numbers",
    "nu": "Numbers",
    "nm": "Numbers",
    "nb": "Numbers",
    "deuteronomy": "Deuteronomy",
    "deut": "Deuteronomy",
    "de": "Deuteronomy",
    "dt": "Deuteronomy",
    "joshua": "Joshua",
    "josh": "Joshua",
    "jos": "Joshua",
    "jsh": "Joshua",
    "judges": "Judges",
    "judg": "Judges",
    "jdg": "Judges",
    "jg": "Judges",
    "jdgs": "Judges",
    "ruth": "Ruth",
    "rth": "Ruth",
    "ru": "Ruth",
    # --- Add programmatically ---
    "ezra": "Ezra",
    "ezr": "Ezra",
    "ez": "Ezra",
    "nehemiah": "Nehemiah",
    "neh": "Nehemiah",
    "ne": "Nehemiah",
    "esther": "Esther",
    "est": "Esther",
    "esth": "Esther",
    "es": "Esther",
    "job": "Job",
    "jb": "Job",
    "psalm": "Psalm",
    "psalms": "Psalm",
    "ps": "Psalm",
    "pslm": "Psalm",
    "psa": "Psalm",
    "psm": "Psalm",
    "pss": "Psalm",
    "proverbs": "Proverbs",
    "prov": "Proverbs",
    "pro": "Proverbs",
    "prv": "Proverbs",
    "pr": "Proverbs",
    "ecclesiastes": "Ecclesiastes",
    "eccles": "Ecclesiastes",
    "eccle": "Ecclesiastes",
    "ecc": "Ecclesiastes",
    "ec": "Ecclesiastes",
    "song of solomon": "Song of Solomon",
    "song": "Song of Solomon",
    "song of songs": "Song of Solomon",
    "sos": "Song of Solomon",
    "so": "Song of Solomon",
    "canticle of canticles": "Song of Solomon",
    "canticles": "Song of Solomon",
    "cant": "Song of Solomon",
    "isaiah": "Isaiah",
    "isa": "Isaiah",
    "is": "Isaiah",
    "jeremiah": "Jeremiah",
    "jer": "Jeremiah",
    "je": "Jeremiah",
    "jr": "Jeremiah",
    "lamentations": "Lamentations",
    "lam": "Lamentations",
    "la": "Lamentations",
    "ezekiel": "Ezekiel",
    "ezek": "Ezekiel",
    "eze": "Ezekiel",
    "ezk": "Ezekiel",
    "daniel": "Daniel",
    "dan": "Daniel",
    "da": "Daniel",
    "dn": "Daniel",
    "hosea": "Hosea",
    "hos": "Hosea",
    "ho": "Hosea",
    "joel": "Joel",
    "jl": "Joel",
    "amos": "Amos",
    "am": "Amos",
    "obadiah": "Obadiah",
    "obad": "Obadiah",
    "ob": "Obadiah",
    "jonah": "Jonah",
    "jnh": "Jonah",
    "jon": "Jonah",
    "micah": "Micah",
    "mic": "Micah",
    "mc": "Micah",
    "nahum": "Nahum",
    "nah": "Nahum",
    "na": "Nahum",
    "habakkuk": "Habakkuk",
    "hab": "Habakkuk",
    "hb": "Habakkuk",
    "zephaniah": "Zephaniah",
    "zeph": "Zephaniah",
    "zep": "Zephaniah",
    "zp": "Zephaniah",
    "haggai": "Haggai",
    "hag": "Haggai",
    "hg": "Haggai",
    "zechariah": "Zechariah",
    "zech": "Zechariah",
    "zec": "Zechariah",
    "zc": "Zechariah",
    "malachi": "Malachi",
    "mal": "Malachi",
    "ml": "Malachi",
    "matthew": "Matthew",
    "matt": "Matthew",
    "mt": "Matthew",
    "mark": "Mark",
    "mrk": "Mark",
    "mar": "Mark",
    "mk": "Mark",
    "mr": "Mark",
    "marc": "Mark",
    "luke": "Luke",
    "luk": "Luke",
    "lk": "Luke",
    "john": "John",
    "joh": "John",
    "jhn": "John",
    "jn": "John",
    "acts": "Acts",
    "act": "Acts",
    "ac": "Acts",
    "romans": "Romans",
    "rom": "Romans",
    "ro": "Romans",
    "rm": "Romans",
    # --- Add programmatically ---
    "galatians": "Galatians",
    "gal": "Galatians",
    "ga": "Galatians",
    "ephesians": "Ephesians",
    "eph": "Ephesians",
    "ephes": "Ephesians",
    "philippians": "Philippians",
    "phillipians": "Philippians",
    "philipians": "Philippians",
    "phillippians": "Philippians",
    "phil": "Philippians",
    "php": "Philippians",
    "pp": "Philippians",
    "colossians": "Colossians",
    "col": "Colossians",
    "co": "Colossians",
    # --- Add programmatically ---
    "titus": "Titus",
    "tit": "Titus",
    "ti": "Titus",
    "philemon": "Philemon",
    "philem": "Philemon",
    "phm": "Philemon",
    "pm": "Philemon",
    "hebrews": "Hebrews",
    "heb": "Hebrews",
    "james": "James",
    "jas": "James",
    "jm": "James",
    # --- Add programmatically ---
    "jude": "Jude",
    "jud": "Jude",
    "Jd": "Jude",
    "revelation": "Revelation",
    "revelations": "Revelation",
    "rev": "Revelation",
    "re": "Revelation",
    "the revelation": "Revelation",
}
for _first in ["1", "i", "1st", "first"]:
    for _book in ["samuel", "sam", "sa", "sm", "s"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 Samuel"
        _canonical_book_name_dict[f"1{_book}"] = "1 Samuel"
    for _book in ["kings", "king", "kgs", "ki", "kin"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 Kings"
        _canonical_book_name_dict[f"1{_book}"] = "1 Kings"
    for _book in ["chronicles", "chron", "chr", "ch"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 Chronicles"
        _canonical_book_name_dict[f"1{_book}"] = "1 Chronicles"
    for _book in ["corinthians", "cor", "co"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 Corinthians"
        _canonical_book_name_dict[f"1{_book}"] = "1 Corinthians"
    for _book in ["thessalonians", "thess", "thes", "th"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 Thessalonians"
        _canonical_book_name_dict[f"1{_book}"] = "1 Thessalonians"
    for _book in ["timothy", "tim", "ti"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 Timothy"
        _canonical_book_name_dict[f"1{_book}"] = "1 Timothy"
    for _book in ["peter", "pet", "pe", "pt", "p"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 Peter"
        _canonical_book_name_dict[f"1{_book}"] = "1 Peter"
    for _book in ["john", "jhn", "joh", "jn", "jo", "j"]:
        _canonical_book_name_dict[f"{_first} {_book}"] = "1 John"
        _canonical_book_name_dict[f"1{_book}"] = "1 John"
for _second in ["2", "ii", "2nd", "second"]:
    for _book in ["samuel", "sam", "sa", "sm", "s"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 Samuel"
        _canonical_book_name_dict[f"2{_book}"] = "2 Samuel"
    for _book in ["kings", "king", "kgs", "ki", "kin"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 Kings"
        _canonical_book_name_dict[f"2{_book}"] = "2 Kings"
    for _book in ["chronicles", "chron", "chr", "ch"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 Chronicles"
        _canonical_book_name_dict[f"2{_book}"] = "2 Chronicles"
    for _book in ["corinthians", "cor", "co"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 Corinthians"
        _canonical_book_name_dict[f"2{_book}"] = "2 Corinthians"
    for _book in ["thessalonians", "thess", "thes", "th"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 Thessalonians"
        _canonical_book_name_dict[f"2{_book}"] = "2 Thessalonians"
    for _book in ["timothy", "tim", "ti"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 Timothy"
        _canonical_book_name_dict[f"2{_book}"] = "2 Timothy"
    for _book in ["peter", "pet", "pe", "pt", "p"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 Peter"
        _canonical_book_name_dict[f"2{_book}"] = "2 Peter"
    for _book in ["john", "jhn", "joh", "jn", "jo", "j"]:
        _canonical_book_name_dict[f"{_second} {_book}"] = "2 John"
        _canonical_book_name_dict[f"2{_book}"] = "2 John"
for _third in ["3", "iii", "3rd", "third"]:
    for _book in ["john", "jhn", "joh", "jn", "jo", "j"]:
        _canonical_book_name_dict[f"{_third} {_book}"] = "3 John"
        _canonical_book_name_dict[f"3{_book}"] = "3 John"

# endregion


@dataclass(frozen=True)
class BibleVerse:
    book: str
    chapter: int
    verse: int
    translation: str

    _CANONICAL_BOOK_NAME = _canonical_book_name_dict

    def __str__(self) -> str:
        return f"{self.book} {self.chapter}:{self.verse} ({self.translation})"

    @staticmethod
    def parse(text: str) -> Optional[Tuple[List[BibleVerse], str]]:
        try:
            books_regex = (
                "(" + "|".join(BibleVerse._CANONICAL_BOOK_NAME.keys()) + ")\\.?"
            )
            chapter_regex = r"(\d\d?\d?)"
            verse_range_regex = r"(?:\d{1,3}(?:-\d{1,3})?)"
            verses_regex = f"({verse_range_regex}(?:,{verse_range_regex})*)"
            # All the translations available on BibleGateway as of 2023-09-17
            translations = "KJ21|ASV|AMP|AMPC|BRG|CSB|CEB|CJB|CEV|DARBY|DLNT|DRA|ERV|EHV|ESV|ESVUK|EXB|GNV|GW|GNT|HCSB|ICB|ISV|PHILLIPS|JUB|KJV|AKJV|LSB|LEB|TLB|MSG|MEV|MOUNCE|NOG|NABRE|NASB|NASB1995|NCB|NCV|NET|NIRV|NIV|NIVUK|NKJV|NLV|NLT|NMB|NRSVA|NRSVACE|NRSVCE|NRSVUE|NTE|OJB|RGT|RSV|RSVCE|TLV|VOICE|WEB|WE|WYC|YLT"
            translation_regex = r"(?:\s+\(?(" + translations + r")\)?)?"
            verse_regex = re.compile(
                f"{books_regex} {chapter_regex}\\s*:\\s*{verses_regex}{translation_regex}(.*)".replace(
                    " ", r"\s+"
                ),
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
        book = book.strip()
        if book.endswith("."):
            book = book[:-1]
        book = re.sub(r"\s+", " ", book)
        book = book.lower()
        return BibleVerse._CANONICAL_BOOK_NAME[book]

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
            text = "\n".join([p.get_attribute("innerText") for p in paragraphs])
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
            checkbox_name = checkbox.get_attribute("name")
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


IMG_WIDTH = 1920
IMG_HEIGHT = 1080
OUTER_MARGIN = 100
INNER_MARGIN = 25
FONT_FAMILY = ["Helvetica", "Calibri", "sans-serif"]
FONT_MANAGER = FontManager()
LT_BODY_FONT = make_font(
    family=FONT_FAMILY, style="normal", size=48, manager=FONT_MANAGER
)
LT_SUBTITLE_FONT = make_font(
    family=FONT_FAMILY, style="oblique", size=40, manager=FONT_MANAGER
)
FS_BODY_FONT = make_font(
    family=FONT_FAMILY, style="normal", size=72, manager=FONT_MANAGER
)
FS_SUBTITLE_FONT = make_font(
    family=FONT_FAMILY, style="oblique", size=60, manager=FONT_MANAGER
)


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
            self._generate_fullscreen_slide_with_footer(
                b, body_font=FS_BODY_FONT, footer_font=FS_SUBTITLE_FONT
            )
            if b.footer_text
            else self._generate_fullscreen_slide_without_footer(b, font=FS_BODY_FONT)
            for b in blueprints
        ]

    def generate_lower_third_slide(
        self, blueprints: List[SlideBlueprint], show_backdrop: bool
    ) -> List[Slide]:
        return [
            self._generate_lower_third_slide_with_footer(
                b, show_backdrop, body_font=LT_BODY_FONT, footer_font=LT_SUBTITLE_FONT
            )
            if b.footer_text
            else self._generate_lower_third_slide_without_footer(
                b, show_backdrop, font=LT_BODY_FONT
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
