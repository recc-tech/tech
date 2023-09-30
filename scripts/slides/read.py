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
