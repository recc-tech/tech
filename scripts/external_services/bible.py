from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import quote_plus

import lxml.etree as lx
import requests

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
                f"{books_regex} {chapter_regex}\\s*(?:\\s|:)\\s*{verses_regex}{translation_regex}(.*)".replace(
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
    def find(self, verse: BibleVerse) -> str:
        url = _get_url(verse)
        response = requests.get(url)
        if response.status_code // 100 != 2:
            raise ValueError(
                f"Request to {url} failed with status code {response.status_code}."
            )

        root = lx.HTML(response.text)
        paragraphs = root.xpath("//div[contains(@class, 'passage-text')]//p")
        if len(paragraphs) == 0:
            raise ValueError(f"Failed to find the text for the verse '{verse}'.")
        text = "\n".join(_get_verse_text(p) for p in paragraphs)
        return _normalize(text)


def _get_url(verse: BibleVerse) -> str:
    search = quote_plus(f"{verse.book} {verse.chapter}:{verse.verse}")
    return f"https://www.biblegateway.com/passage/?search={search}&version={verse.translation}&interface=print"


def _get_verse_text(e: lx._Element) -> str:  # pyright: ignore[reportPrivateUsage]
    text = "\n" if e.tag == "br" else (e.text or "")
    for ee in e:
        if not _should_skip(ee):
            text += _get_verse_text(ee)
        text += ee.tail or ""
    return text


def _should_skip(e: lx._Element) -> bool:  # pyright: ignore[reportPrivateUsage]
    cls = e.get("class") or ""
    return (
        "versenum" in cls
        or "chapternum" in cls
        or "footnote" in cls
        or "crossreference" in cls
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
