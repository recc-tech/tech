from __future__ import annotations

import html
import json
import re
import typing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Set, Type, TypeVar

from autochecklist import Messenger, ProblemLevel
from config import Config
from external_services import (
    ItemNote,
    Plan,
    PlanItem,
    PlanningCenterClient,
    PlanSection,
    Song,
)


@dataclass(frozen=True)
class AnnotatedSong:
    song: Song
    notes: List[ItemNote]
    description: str


@dataclass(frozen=True)
class AnnotatedItem:
    content: str
    notes: List[ItemNote]


@dataclass(frozen=True)
class PlanItemsSummary:
    plan: Plan
    walk_in_slides: List[str]
    announcements: List[str]
    opener_video: Optional[AnnotatedItem]
    bumper_video: Optional[AnnotatedItem]
    announcements_video: Optional[AnnotatedItem]
    songs: List[AnnotatedSong]
    message_notes: Optional[AnnotatedItem]
    num_visuals_notes: int


T = TypeVar("T")


def _get_one(
    items: List[T], messenger: Messenger, name: str, missing_ok: bool = False
) -> Optional[T]:
    if len(items) == 0:
        if not missing_ok:
            messenger.log_problem(ProblemLevel.WARN, f"No {name} found.")
        return None
    elif len(items) == 1:
        return items[0]
    else:
        messenger.log_problem(
            ProblemLevel.WARN, f"Found {len(items)} items that look like {name}."
        )
        return None


def _remove_unnecessary_notes(sections: List[PlanSection]) -> List[PlanSection]:
    new_sections: List[PlanSection] = []
    for s in sections:
        if not _is_message_section(s):
            new_sections.append(s)
        else:
            new_items: List[PlanItem] = []
            for itm in s.items:
                new_notes = [
                    n for n in itm.notes if not n.contents.lower() == "name slide"
                ]
                new_itm = PlanItem(
                    title=itm.title,
                    description=itm.description,
                    song=itm.song,
                    notes=new_notes,
                )
                new_items.append(new_itm)
            new_sections.append(PlanSection(title=s.title, items=new_items))
    return new_sections


def _filter_notes_by_category(
    notes: List[ItemNote], categories: List[str]
) -> List[ItemNote]:
    return [n for n in notes if n.category in categories]


def _get_announcement_slide_names(item: PlanItem) -> List[str]:
    lines = item.description.splitlines()
    # If any lines are numbered, only keep the numbered ones
    numbered_line_matches = [re.fullmatch(r"\d+\. (.*)", l) for l in lines]
    if any(numbered_line_matches):
        lines = [m[1] for m in numbered_line_matches if m is not None]
    # If any lines end with " - Slide", only keep those
    suffix_regex = r"(.*)\s+-\s+slide|(.*\s+-\s+title slide)"
    suffix_matches = [re.fullmatch(suffix_regex, l, re.IGNORECASE) for l in lines]
    if any(suffix_matches):
        lines = [m[1] or m[2] for m in suffix_matches if m is not None]
    return lines


def _merge(lst1: List[T], lst2: List[T]) -> List[T]:
    """
    Add all elements of `lst2` to `lst1` while preserving the order and avoiding
    duplicates.
    """
    new_list = list(lst1)
    for n in lst2:
        if n not in new_list:
            new_list.append(n)
    return new_list


def _get_walk_in_slides(items: List[PlanItem]) -> List[str]:
    matches = [
        i for i in items if re.search("rotating announcements", i.title, re.IGNORECASE)
    ]
    slide_names: List[str] = []
    for itm in matches:
        lines = itm.description.splitlines()
        ms = [re.fullmatch(r"\d+\. (.*)", l) for l in lines]
        names = [m[1] for m in ms if m is not None]
        slide_names = _merge(slide_names, names)
    return slide_names


def _get_announcements(items: List[PlanItem]) -> List[str]:
    pattern = "(mc hosts?|announcements|mc hosts?)"
    matches = [
        i
        for i in items
        if re.search(pattern, i.title, re.IGNORECASE)
        and not re.search("rotating announcements", i.title, re.IGNORECASE)
        and not re.search("video announcements", i.title, re.IGNORECASE)
    ]
    slide_names: List[str] = []
    for itm in matches:
        names = _get_announcement_slide_names(itm)
        slide_names = _merge(slide_names, names)
    return slide_names


def _get_opener_video(
    sections: List[PlanSection], messenger: Messenger, note_categories: List[str]
) -> Optional[AnnotatedItem]:
    matching_sections = [
        s for s in sections if re.search("opener video", s.title, re.IGNORECASE)
    ]
    sec = _get_one(matching_sections, messenger, "opener video section")
    itm = None if sec is None else _get_one(sec.items, messenger, "opener video")
    return (
        None
        if itm is None
        else AnnotatedItem(
            itm.title, _filter_notes_by_category(itm.notes, note_categories)
        )
    )


def _get_bumper_video(
    sec: PlanSection, messenger: Messenger, note_categories: List[str]
) -> Optional[AnnotatedItem]:
    matches = [i for i in sec.items if re.search("bumper", i.title, re.IGNORECASE)]
    itm = _get_one(matches, messenger, "bumper video")
    name = None if itm is None else itm.title
    prefix = "bumper video: "
    if name and name.lower().startswith(prefix):
        name = name[len(prefix) :]
    return (
        None
        if itm is None or name is None
        else AnnotatedItem(name, _filter_notes_by_category(itm.notes, note_categories))
    )


def _get_announcements_video(
    items: List[PlanItem], messenger: Messenger, note_categories: List[str]
) -> Optional[AnnotatedItem]:
    matches = [
        i for i in items if re.search("video announcements", i.title, re.IGNORECASE)
    ]
    itm = _get_one(matches, messenger, "announcements video", missing_ok=True)
    return (
        None
        if itm is None
        else AnnotatedItem(
            itm.title, _filter_notes_by_category(itm.notes, note_categories)
        )
    )


def _is_message_section(s: PlanSection) -> bool:
    return s.title.lower() == "message"


def _get_message_section(
    sections: List[PlanSection], messenger: Messenger
) -> Optional[PlanSection]:
    matching_sections = [s for s in sections if _is_message_section(s)]
    sec = _get_one(matching_sections, messenger, "message section")
    return sec


def _get_message_notes(
    sec: PlanSection, messenger: Messenger, note_categories: List[str]
) -> Optional[AnnotatedItem]:
    matches = [
        i for i in sec.items if re.search("message title:", i.title, re.IGNORECASE)
    ]
    itm = _get_one(matches, messenger, "message notes")
    if itm is None:
        return None
    else:
        notes = _filter_notes_by_category(itm.notes, note_categories)
        return AnnotatedItem(content=itm.description.strip(), notes=notes)


def _get_songs(
    sections: List[PlanSection], note_categories: List[str]
) -> List[AnnotatedSong]:
    matching_items = [
        i
        for s in sections
        for i in s.items
        if i.song is not None or re.search(r"worship", s.title, re.IGNORECASE)
    ]
    songs: List[AnnotatedSong] = []
    for i in matching_items:
        song = i.song or Song(ccli=None, title=i.title, author=None)
        notes = _filter_notes_by_category(i.notes, note_categories)
        songs.append(AnnotatedSong(song, notes=notes, description=i.description))
    return songs


def _find_duplicate_lines(sermon: str) -> Set[str]:
    lines: Set[str] = set()
    duplicate_lines: Set[str] = set()
    for line in sermon.split("\n"):
        normalized_line = re.sub(r"\s+", " ", line).strip().lower()
        if not normalized_line:
            continue
        if normalized_line in lines:
            duplicate_lines.add(normalized_line)
        else:
            lines.add(normalized_line)
    return duplicate_lines


def _validate_message_notes(original_notes: AnnotatedItem) -> AnnotatedItem:
    warnings: List[ItemNote] = []
    duplicate_lines = _find_duplicate_lines(original_notes.content)
    if duplicate_lines:
        lines_str = ", ".join([f'"{x}"' for x in duplicate_lines])
        warnings.append(
            ItemNote(
                category="Warning",
                contents=(
                    f"There are duplicate lines in the sermon notes ({lines_str})."
                    " Check with Pastor Lorenzo that this is intentional."
                ),
            )
        )
    return AnnotatedItem(
        content=original_notes.content, notes=original_notes.notes + warnings
    )


def get_plan_summary(
    client: PlanningCenterClient, messenger: Messenger, config: Config, dt: date
) -> PlanItemsSummary:
    plan = client.find_plan_by_date(dt)
    sections = client.find_plan_items(
        plan.id, include_songs=True, include_item_notes=True
    )
    sections = _remove_unnecessary_notes(sections)
    items = [i for s in sections for i in s.items]
    walk_in_slides = _get_walk_in_slides(items)
    opener_video = _get_opener_video(
        sections, messenger, note_categories=config.plan_summary_note_categories
    )
    announcements = _get_announcements(items)
    announcements = [
        a for a in announcements if a.lower() not in config.announcements_to_ignore
    ]
    announcements_video = _get_announcements_video(
        items, messenger, note_categories=config.plan_summary_note_categories
    )
    msg_sec = _get_message_section(sections, messenger)
    if msg_sec is None:
        bumper_video = None
        message_notes = None
    else:
        bumper_video = _get_bumper_video(
            msg_sec, messenger, note_categories=config.plan_summary_note_categories
        )
        message_notes = _get_message_notes(
            msg_sec, messenger, note_categories=config.plan_summary_note_categories
        )
        if message_notes is not None:
            message_notes = _validate_message_notes(message_notes)
    songs = _get_songs(sections, note_categories=config.plan_summary_note_categories)
    all_notes = [n for s in sections for i in s.items for n in i.notes]
    visuals_notes = _filter_notes_by_category(
        all_notes, config.plan_summary_note_categories
    )
    return PlanItemsSummary(
        plan=plan,
        walk_in_slides=walk_in_slides,
        announcements=announcements,
        opener_video=opener_video,
        bumper_video=bumper_video,
        announcements_video=announcements_video,
        songs=songs,
        message_notes=message_notes,
        num_visuals_notes=len(visuals_notes),
    )


def _cast(t: Type[T], x: object) -> T:
    if not isinstance(x, t):
        raise TypeError(
            f"Expected object of type {t}, but found object of type {type(x).__name__}."
        )
    return x


def _parse_note(note: object) -> ItemNote:
    note = typing.cast(dict[object, object], _cast(dict, note))
    return ItemNote(
        category=_cast(str, note["category"]),
        contents=_cast(str, note["contents"]),
    )


def _parse_annotated_item(data: object) -> Optional[AnnotatedItem]:
    if data is None:
        return None
    data = typing.cast(dict[object, object], _cast(dict, data))
    content = _cast(str, data["content"])
    raw_notes = typing.cast(list[object], _cast(list, data["notes"]))
    notes = [_parse_note(n) for n in raw_notes]
    return AnnotatedItem(content=content, notes=notes)


def _parse_song(song: object) -> Song:
    song = typing.cast(dict[object, object], _cast(dict, song))
    ccli = song["ccli"]
    if ccli is not None:
        ccli = _cast(str, song["ccli"])
    title = _cast(str, song["title"])
    author = song["author"]
    if author is not None:
        author = _cast(str, author)
    return Song(ccli=ccli, title=title, author=author)


def _parse_annotated_song(song: object) -> AnnotatedSong:
    song = typing.cast(dict[object, object], _cast(dict, song))
    raw_notes = typing.cast(list[object], _cast(list, song["notes"]))
    return AnnotatedSong(
        song=_parse_song(song["song"]),
        notes=[_parse_note(n) for n in raw_notes],
        description=str(song["description"]),
    )


def load_plan_summary(path: Path) -> PlanItemsSummary:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    opener_vid = (
        _parse_annotated_item(data["opener_video"]) if "opener_video" in data else None
    )
    bumper_vid = (
        _parse_annotated_item(data["bumper_video"]) if "bumper_video" in data else None
    )
    announcements_vid = (
        _parse_annotated_item(data["announcements_video"])
        if "announcements_video" in data
        else None
    )
    songs = [_parse_annotated_song(s) for s in data["songs"]]
    message_notes = _parse_annotated_item(data["message_notes"])
    return PlanItemsSummary(
        plan=Plan(
            id=data["plan"]["id"],
            series_title=data["plan"]["series_title"],
            title=data["plan"]["title"],
            date=datetime.strptime(data["plan"]["date"], "%Y-%m-%d").date(),
            web_page_url=data["plan"]["web_page_url"],
        ),
        walk_in_slides=data["walk_in_slides"],
        announcements=data["announcements"],
        opener_video=opener_vid,
        bumper_video=bumper_vid,
        announcements_video=announcements_vid,
        songs=songs,
        message_notes=message_notes,
        num_visuals_notes=data["num_visuals_notes"],
    )


_SUPERHEADER_CLS = "superheader"
_HEADER_CLS = "header-row"
_EVEN_ROW_CLS = "even-row"
_ODD_ROW_CLS = "odd-row"
_NOTES_TITLE_CLS = "notes-title"
_NOTES_WARNING_CLS = "notes-warning"
_ICON_PATH = Path(__file__).resolve().parent.parent.parent.joinpath("icon_32x32.png")


def _indent(code: str, n: int) -> str:
    return "\n".join([f"{'    ' * n}{c}" for c in code.split("\n")])


def _escape(text: str) -> str:
    return html.escape(text).replace("\r\n", "\n").replace("\n", "<br>")


def _show_notes(notes: List[ItemNote]) -> str:
    notes_str = [
        f"<span class='{_NOTES_TITLE_CLS}'>⚠️ {_escape(n.category)}</span><br>\n{_escape(n.contents)}"
        for n in notes
    ]
    return "<br>".join(notes_str)


@dataclass
class HtmlTable:
    cls: str
    col_widths: List[str]
    header: Optional[List[str]]
    rows: List[List[str]]
    indent: bool = True

    def __post_init__(self) -> None:
        self._check_ncols()

    def _check_ncols(self) -> None:
        ncols = len(self.col_widths)
        if self.header is not None and len(self.header) != ncols:
            raise ValueError("Number of columns in header is not as expected.")
        for i, r in enumerate(self.rows):
            if len(r) != ncols:
                raise ValueError(
                    f"Number of columns in row {i} is not as expected. Expected {ncols} but found {len(r)}."
                )

    def to_css(self) -> str:
        return f"""
.{self.cls} {{
    display: grid;
    border: 2px solid var(--dark-background-color);
    border-top: 0;
    grid-template-columns: {' '.join(self.col_widths)};
}}
""".strip()

    def to_html(self) -> str:
        divs: List[str] = []
        if self.header is not None:
            divs += [f"<div class='{_HEADER_CLS}'>{h}</div>" for h in self.header]
        for i, row in enumerate(self.rows):
            cls = _EVEN_ROW_CLS if i % 2 == 0 else _ODD_ROW_CLS
            divs += [f"<div class='{cls}'>{x}</div>" for x in row]
        divs_str = "\n".join(divs)
        return f"""
<div class="{self.cls}">
{_indent(divs_str, 1 if self.indent else 0)}
</div>
""".strip()


def _make_walk_in_slides_list(slides: List[str]) -> str:
    items = "\n".join([f"<li>{_escape(s)}</li>" for s in slides])
    return f"""
<ul>
{_indent(items, 1)}
</ul>
""".strip()


def _make_announcements_list(slides: List[str]) -> str:
    items = "\n".join([f"<li>{_escape(s)}</li>" for s in slides])
    return f"""
<ul>
{_indent(items, 1)}
</ul>
""".strip()


def _make_videos_table(
    opener: Optional[AnnotatedItem],
    bumper: Optional[AnnotatedItem],
    announcements: Optional[AnnotatedItem],
) -> HtmlTable:
    missing = "<span class='missing'>None found</span>"
    opener_name = opener.content if opener is not None else missing
    opener_notes = _show_notes(opener.notes) if opener is not None else ""
    bumper_name = bumper.content if bumper is not None else missing
    bumper_notes = _show_notes(bumper.notes) if bumper is not None else ""
    announcements_name = announcements.content if announcements is not None else missing
    announcements_notes = (
        _show_notes(announcements.notes) if announcements is not None else ""
    )
    rows = [
        ["Opener", _escape(opener_name), opener_notes],
        ["Bumper", _escape(bumper_name), bumper_notes],
        ["Announcements", _escape(announcements_name), announcements_notes],
    ]
    return HtmlTable(
        cls="videos-table",
        col_widths=["min-content", "1fr", "1fr"],
        header=None,
        rows=rows,
    )


def _make_songs_table(songs: List[AnnotatedSong]) -> HtmlTable:
    rows = [
        [
            _escape(s.song.ccli or ""),
            _show_notes(s.notes),
            _escape(s.song.title or ""),
            _escape(s.song.author or ""),
            _escape(s.description or ""),
        ]
        for s in songs
    ]
    col_widths = ["min-content", "3fr", "2fr", "3fr", "3fr"]
    header = ["CCLI", "Notes", "Title", "Author", "Description"]
    # No notes
    if all(not r[1] for r in rows):
        col_widths[1] = "min-content"
    return HtmlTable(
        cls="songs-table",
        col_widths=col_widths,
        header=header,
        rows=rows,
    )


def _make_message_table(message: Optional[AnnotatedItem]) -> HtmlTable:
    sermon_notes = message.content if message else ""
    has_sermon_notes = bool(sermon_notes.strip())
    sermon_notes = (
        f"<details><summary>Show notes</summary><pre id='message-notes'>{html.escape(sermon_notes)}</pre></details>"
        if sermon_notes
        else "<span class='missing'>No Notes Available</span>"
    )
    disabled = "disabled" if not has_sermon_notes else ""
    btn = f"<button id='copy-btn' onclick='copyMessageNotes()' {disabled}>Copy</button><br><span id='copy-confirm' style='visibility: hidden;'>Copied &check;</span>"
    visuals_notes = _show_notes(message.notes) if message is not None else ""
    row = [btn, sermon_notes, visuals_notes]
    return HtmlTable(
        cls="message-table",
        col_widths=["min-content", "1fr", "1fr"],
        header=None,
        rows=[row],
        indent=False,
    )


def plan_summary_to_html(summary: PlanItemsSummary) -> str:
    title = (
        _escape(f"{summary.plan.series_title}: {summary.plan.title}")
        if summary.plan.series_title
        else _escape(summary.plan.title)
    )
    subtitle = _escape(summary.plan.date.strftime("%B %d, %Y"))
    walk_in_slides_list = _make_walk_in_slides_list(summary.walk_in_slides)
    announcements_list = _make_announcements_list(summary.announcements)
    videos_table = _make_videos_table(
        opener=summary.opener_video,
        bumper=summary.bumper_video,
        announcements=summary.announcements_video,
    )
    songs_table = _make_songs_table(songs=summary.songs)
    message_table = _make_message_table(summary.message_notes)
    is_or_are = "is" if summary.num_visuals_notes == 1 else "are"
    note_or_notes = "note" if summary.num_visuals_notes == 1 else "notes"
    it_or_they = "it" if summary.num_visuals_notes == 1 else "they"
    return f"""
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8" />
        <title>Plan Summary</title>
        <link rel='shortcut icon' href='{_ICON_PATH.as_posix()}' />
        <style>
            html {{
                /* Same as Planning Center */
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--background-color);
                /* Same as the website */
                --highlight-color: #1a7ee5;
                --dim-highlight-color: #8ea0b7;
                --background-color: #fafafa;
                --dark-background-color: rgb(235, 235, 235);
            }}
            body {{
                margin: 0;
            }}
            header {{
                background-color: var(--highlight-color);
                color: white;
                padding: 1em;
            }}
            #main-content {{
                margin: 1em 1em 10em 1em;
            }}
            h1 {{
                font-size: x-large;
            }}
            h2 {{
                font-size: large;
            }}
            .notes-title {{
                font-weight: bolder;
            }}
            .missing {{
                color: red;
            }}
            .superheader, .header-row, .even-row, .odd-row {{
                padding: 0.25em 0.5em 0.25em 0.5em;
            }}
            .{_SUPERHEADER_CLS} {{
                font-size: x-large;
                font-weight: bolder;
                background-color: var(--dim-highlight-color);
                border: 2px solid var(--dark-background-color);
                border-bottom: 0;
                color: white;
                margin-top: 0.5em;
            }}
            .{_HEADER_CLS} {{
                font-weight: bolder;
                font-size: large;
                background-color: var(--dim-highlight-color);
                color: white;
            }}
            .{_EVEN_ROW_CLS} {{
                background-color: var(--background-color);
            }}
            .{_ODD_ROW_CLS} {{
                background-color: var(--dark-background-color);
            }}
            #copy-btn {{
                font-size: large;
            }}
            #message-notes {{
                font-family: inherit;
            }}
            .{_NOTES_WARNING_CLS} {{
                visibility: {'visible' if summary.num_visuals_notes > 0 else 'hidden'};
                border: 2px solid #b57b0e;
                color: #b57b0e;
                background-color: #fffaa0;
                border-radius: 5px;
                padding: 0.5em;
            }}
{_indent(videos_table.to_css(), 3)}
{_indent(songs_table.to_css(),3)}
{_indent(message_table.to_css(),3)}
        </style>
        <script>
            function copyMessageNotes() {{
                const messageNotes = document.getElementById("message-notes").textContent;
                navigator.clipboard.writeText(messageNotes);
                const check = document.getElementById("copy-confirm");
                check.style.visibility = "visible";
            }}
        </script>
    </head>
    <body>
        <header>
            <h1>{title}</h1>
            <h2>{subtitle}</h2>
        </header>
        <div id='main-content'>
            <div class="{_NOTES_WARNING_CLS}">
                Heads up!
                There {is_or_are} {summary.num_visuals_notes} {note_or_notes}
                for the visuals team in the plan.
                {it_or_they.capitalize()} might call for adjustments to the
                presentations, such as changes to songs lyrics.
                If fewer notes are shown here, check Planning Center.
                Make sure the visuals notes are visible by clicking on the
                button at the top right-hand corner with the three vertical bars
                and ensure the "Visuals" checkbox is checked.
            </div>
            <div class="{_SUPERHEADER_CLS}">Walk-in Slides</div>
{_indent(walk_in_slides_list, 3)}
            <div class="{_SUPERHEADER_CLS}">Announcements</div>
{_indent(announcements_list, 3)}
            <div class="{_SUPERHEADER_CLS}">Videos</div>
{_indent(videos_table.to_html(), 3)}
            <div class='{_SUPERHEADER_CLS}'>Songs</div>
{_indent(songs_table.to_html(), 3)}
            <div class='{_SUPERHEADER_CLS}'>Message</div>
{message_table.to_html()}
        </div>
    </body>
</html>
""".lstrip()
