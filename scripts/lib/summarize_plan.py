from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, TypeVar

from autochecklist import Messenger, ProblemLevel
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


@dataclass(frozen=True)
class AnnotatedItem:
    content: str
    notes: List[ItemNote]


@dataclass(frozen=True)
class PlanItemsSummary:
    plan: Plan
    # TODO: Notes for announcements slides?
    walk_in_slides: List[str]
    announcements: List[str]
    opener_video: Optional[AnnotatedItem]
    bumper_video: Optional[AnnotatedItem]
    announcements_video: Optional[AnnotatedItem]
    songs: List[AnnotatedSong]
    message_notes: Optional[AnnotatedItem]


T = TypeVar("T")


def _get_one(items: List[T], messenger: Messenger, name: str) -> Optional[T]:
    if len(items) == 0:
        messenger.log_problem(ProblemLevel.WARN, f"No {name} found.")
        return None
    elif len(items) == 1:
        return items[0]
    else:
        messenger.log_problem(
            ProblemLevel.WARN, f"Found {len(items)} items that look like {name}."
        )
        return None


def _filter_notes(notes: List[ItemNote]) -> List[ItemNote]:
    return [n for n in notes if n.category == "Visuals"]


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


def _get_walk_in_slides(items: List[PlanItem], messenger: Messenger) -> List[str]:
    matches = [
        i for i in items if re.search("rotating announcements", i.title, re.IGNORECASE)
    ]
    if len(matches) != 2:
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Found {len(matches)} items that look like lists of rotating announcements.",
        )
    slide_names: List[str] = []
    for itm in matches:
        lines = itm.description.splitlines()
        ms = [re.fullmatch(r"\d+\. (.*)", l) for l in lines]
        names = [m[1] for m in ms if m is not None]
        slide_names = _merge(slide_names, names)
    return slide_names


def _get_announcements(items: List[PlanItem], messenger: Messenger) -> List[str]:
    pattern = "(mc hosts?|announcements|mc hosts?)"
    matches = [
        i
        for i in items
        if re.search(pattern, i.title, re.IGNORECASE)
        and not re.search("rotating announcements", i.title, re.IGNORECASE)
        and not re.search("video announcements", i.title, re.IGNORECASE)
    ]
    if len(matches) != 3:
        titles = [i.title for i in matches]
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Found {len(matches)} items that look like lists of announcements: {', '.join(titles)}.",
        )
    slide_names: List[str] = []
    for itm in matches:
        names = _get_announcement_slide_names(itm)
        slide_names = _merge(slide_names, names)
    return slide_names


def _get_opener_video(
    sections: List[PlanSection], messenger: Messenger
) -> Optional[AnnotatedItem]:
    matching_sections = [
        s for s in sections if re.search("opener video", s.title, re.IGNORECASE)
    ]
    sec = _get_one(matching_sections, messenger, "opener video section")
    itm = None if sec is None else _get_one(sec.items, messenger, "opener video")
    return None if itm is None else AnnotatedItem(itm.title, _filter_notes(itm.notes))


def _get_bumper_video(
    sec: PlanSection, messenger: Messenger
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
        else AnnotatedItem(name, _filter_notes(itm.notes))
    )


def _get_announcements_video(
    items: List[PlanItem], messenger: Messenger
) -> Optional[AnnotatedItem]:
    matches = [
        i for i in items if re.search("video announcements", i.title, re.IGNORECASE)
    ]
    itm = _get_one(matches, messenger, "announcements video")
    return None if itm is None else AnnotatedItem(itm.title, _filter_notes(itm.notes))


def _get_message_section(
    sections: List[PlanSection], messenger: Messenger
) -> Optional[PlanSection]:
    matching_sections = [s for s in sections if s.title.lower() == "message"]
    sec = _get_one(matching_sections, messenger, "message section")
    return sec


def _get_message_notes(
    sec: PlanSection, messenger: Messenger
) -> Optional[AnnotatedItem]:
    matches = [
        i for i in sec.items if re.search("message title:", i.title, re.IGNORECASE)
    ]
    itm = _get_one(matches, messenger, "message notes")
    return (
        None
        if itm is None
        else AnnotatedItem(itm.description.strip(), _filter_notes(itm.notes))
    )


def _get_songs(
    sections: List[PlanSection], messenger: Messenger
) -> List[AnnotatedSong]:
    matching_items = [
        i
        for s in sections
        for i in s.items
        if i.song is not None or re.search(r"worship", s.title, re.IGNORECASE)
    ]
    if len(matching_items) != 5:  # TODO: Move expected numbers of items to config
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Found {len(matching_items)} items that look like songs.",
        )
    songs: List[AnnotatedSong] = []
    for i in matching_items:
        song = i.song or Song(ccli=None, title=i.title, author=None)
        notes = [n for n in i.notes if n.category == "Visuals"]
        songs.append(AnnotatedSong(song, notes))
    return songs


def get_plan_summary(
    client: PlanningCenterClient, messenger: Messenger, dt: date
) -> PlanItemsSummary:
    plan = client.find_plan_by_date(dt)
    sections = client.find_plan_items(
        plan.id, include_songs=True, include_item_notes=True
    )
    items = [i for s in sections for i in s.items]
    walk_in_slides = _get_walk_in_slides(items, messenger)
    opener_video = _get_opener_video(sections, messenger)
    announcements = _get_announcements(items, messenger)
    announcements_video = _get_announcements_video(items, messenger)
    msg_sec = _get_message_section(sections, messenger)
    if msg_sec is None:
        bumper_video = None
        message_notes = None
    else:
        bumper_video = _get_bumper_video(msg_sec, messenger)
        message_notes = _get_message_notes(msg_sec, messenger)
    songs = _get_songs(sections, messenger)
    return PlanItemsSummary(
        plan=plan,
        walk_in_slides=walk_in_slides,
        announcements=announcements,
        opener_video=opener_video,
        bumper_video=bumper_video,
        announcements_video=announcements_video,
        songs=songs,
        message_notes=message_notes,
    )


_SUPERHEADER_CLS = "superheader"
_HEADER_CLS = "header-row"
_VIDEO_TAB_CLS = "videos-table"
_SONG_TAB_CLS = "songs-table"
_MESSAGE_TAB_CLS = "message-notes-table"
_EVEN_ROW_CLS = "even-row"
_ODD_ROW_CLS = "odd-row"
_NOTES_TITLE_CLS = "notes-title"


def _indent(code: str, n: int) -> str:
    return "\n".join([f"{'    ' * n}{c}" for c in code.split("\n")])


def _escape(text: str) -> str:
    return html.escape(text).replace("\r\n", "\n").replace("\n", "<br>")


def _show_notes(notes: List[ItemNote]) -> str:
    notes_str = [
        f"<span class='{_NOTES_TITLE_CLS}'>⚠️ {_escape(n.category)}</span><br>\n{_escape(n.contents)}"
        for n in notes
    ]
    return "\n".join(notes_str)


@dataclass
class HtmlTable:
    cls: str
    ncols: int
    header: Optional[List[str]]
    rows: List[List[str]]

    def _check_ncols(self) -> None:
        if self.header is not None and len(self.header) != self.ncols:
            raise ValueError("Number of columns in header is not as expected.")
        for i, r in enumerate(self.rows):
            if len(r) != self.ncols:
                raise ValueError(
                    f"Number of columns in row {i} is not as expected. Expected {self.ncols} but found {len(r)}."
                )

    def to_html(self) -> str:
        self._check_ncols()
        divs: List[str] = []
        if self.header is not None:
            divs += [f"<div class='{_HEADER_CLS}'>{h}</div>" for h in self.header]
        for i, row in enumerate(self.rows):
            cls = _EVEN_ROW_CLS if i % 2 == 0 else _ODD_ROW_CLS
            divs += [f"<div class='{cls}'>{x}</div>" for x in row]
        divs_str = "\n".join(divs)
        return f"""
<div class="{self.cls}">
{_indent(divs_str, 1)}
</div>
""".strip()


@dataclass
class WalkInSlidesSection:
    slides: List[str]

    def to_html(self) -> str:
        items = "\n".join([f"<li>{_escape(s)}</li>" for s in self.slides])
        return f"""
<div class="{_SUPERHEADER_CLS}">Walk-in Slides</div>
<ul>
{_indent(items, 1)}
</ul>
""".strip()


@dataclass
class AnnouncementsSection:
    slides: List[str]

    def to_html(self) -> str:
        items = "\n".join([f"<li>{_escape(s)}</li>" for s in self.slides])
        return f"""
<div class="{_SUPERHEADER_CLS}">Announcements</div>
<ul>
{_indent(items, 1)}
</ul>
""".strip()


@dataclass
class VideosSection:
    opener: Optional[AnnotatedItem]
    bumper: Optional[AnnotatedItem]
    announcements: Optional[AnnotatedItem]

    def to_html(self) -> str:
        missing = "<span class='missing'>None found</span>"
        opener = self.opener.content if self.opener is not None else missing
        opener_notes = _show_notes(self.opener.notes) if self.opener is not None else ""
        bumper = self.bumper.content if self.bumper is not None else missing
        bumper_notes = _show_notes(self.bumper.notes) if self.bumper is not None else ""
        announcements = (
            self.announcements.content if self.announcements is not None else missing
        )
        announcements_notes = (
            _show_notes(self.announcements.notes)
            if self.announcements is not None
            else ""
        )
        rows = [
            ["Opener", _escape(opener), opener_notes],
            ["Bumper", _escape(bumper), bumper_notes],
            ["Announcements", _escape(announcements), announcements_notes],
        ]
        tab = HtmlTable(cls=_VIDEO_TAB_CLS, ncols=3, header=None, rows=rows)
        return f"""
<div class="{_SUPERHEADER_CLS}">Videos</div>
{tab.to_html()}
""".strip()


@dataclass
class SongSection:
    songs: List[AnnotatedSong]

    def _make_row(self, s: AnnotatedSong) -> List[str]:
        return [
            _escape(s.song.ccli or ""),
            _show_notes(s.notes),
            _escape(s.song.title or ""),
            _escape(s.song.author or ""),
        ]

    def to_html(self) -> str:
        # TODO: Omit notes column if there are no notes?
        rows = [self._make_row(s) for s in self.songs]
        tab = HtmlTable(
            cls=_SONG_TAB_CLS,
            ncols=4,
            header=["CCLI", "Notes", "Title", "Author"],
            rows=rows,
        )
        return f"""
<div class='{_SUPERHEADER_CLS}'>Songs</div>
{tab.to_html()}
""".strip()


@dataclass
class MessageSection:
    message: Optional[AnnotatedItem]

    def to_html(self) -> str:
        sermon_notes = self.message.content if self.message else ""
        has_sermon_notes = bool(sermon_notes.strip())
        sermon_notes = (
            f"<details><summary>Show notes</summary><span id='message-notes'>{_escape(sermon_notes)}</span></details>"
            if sermon_notes
            else "<span class='missing'>No Notes Available</span>"
        )
        disabled = "disabled" if not has_sermon_notes else ""
        btn = f"<button id='copy-btn' onclick='copyMessageNotes()' {disabled}>Copy</button><br><span id='copy-confirm' style='visibility: hidden;'>Copied &check;</span>"
        visuals_notes = (
            _show_notes(self.message.notes) if self.message is not None else ""
        )
        row = [btn, sermon_notes, visuals_notes]
        tab = HtmlTable(cls=_MESSAGE_TAB_CLS, ncols=3, header=None, rows=[row])
        return f"""
<div class='{_SUPERHEADER_CLS}'>Message</div>
{tab.to_html()}
""".strip()


def plan_summary_to_html(summary: PlanItemsSummary) -> str:
    # TODO: Also warn the user if there are extra notes other than the ones for songs?
    title = (
        _escape(f"{summary.plan.series_title}: {summary.plan.title}")
        if summary.plan.series_title
        else _escape(summary.plan.title)
    )
    subtitle = _escape(summary.plan.date.strftime("%B %d, %Y"))
    walk_in_slides_section = WalkInSlidesSection(summary.walk_in_slides)
    announcements_section = AnnouncementsSection(summary.announcements)
    videos_section = VideosSection(
        opener=summary.opener_video,
        bumper=summary.bumper_video,
        announcements=summary.announcements_video,
    )
    songs_section = SongSection(songs=summary.songs)
    message_section = MessageSection(summary.message_notes)
    return f"""
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8" />
        <title>Plan Summary</title>
        <style>
            html {{
                /* Same as Planning Center */
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--background-color);
                /* Same as the website */
                --highlight-color: #1a7ee5;
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
                padding: 0.25em;
            }}
            .{_SUPERHEADER_CLS} {{
                font-size: x-large;
                font-weight: bolder;
                background-color: #8ea0b7;
                border: 2px solid var(--dark-background-color);
                border-bottom: 0;
                color: white;
                margin-top: 0.5em;
            }}
            .{_HEADER_CLS} {{
                font-weight: bolder;
                font-size: large;
                background-color: #8ea0b7;
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
            .{_SONG_TAB_CLS} {{
                display: grid;
                grid-template-columns: 8em 5fr 3fr 3fr;
                border: 2px solid var(--dark-background-color);
                border-top: 0;
            }}
            .{_MESSAGE_TAB_CLS} {{
                display: grid;
                grid-template-columns: min-content 1fr 1fr;
                border: 2px solid var(--dark-background-color);
                border-top: 0;
            }}
            .{_VIDEO_TAB_CLS} {{
                display: grid;
                grid-template-columns: min-content 1fr 1fr;
                border: 2px solid var(--dark-background-color);
                border-top: 0;
            }}
        </style>
        <script>
            function copyMessageNotes() {{
                const messageNotes = document.getElementById("message-notes").innerText;
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
{_indent(walk_in_slides_section.to_html(), 3)}
{_indent(announcements_section.to_html(), 3)}
{_indent(videos_section.to_html(), 3)}
{_indent(songs_section.to_html(), 3)}
{_indent(message_section.to_html(), 3)}
        </div>
    </body>
</html>
""".lstrip()
