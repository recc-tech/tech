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
class PlanItemsSummary:
    plan: Plan
    walk_in_slides: List[str]
    opener_video: str
    announcements: List[str]
    songs: List[AnnotatedSong]
    bumper_video: str
    announcements_video: Optional[str]
    message_notes: str


T = TypeVar("T")


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


def _get_opener_video(sections: List[PlanSection]) -> str:
    matching_sections = [
        s for s in sections if re.search("opener video", s.title, re.IGNORECASE)
    ]
    if len(matching_sections) != 1:
        raise ValueError(
            f"Found {len(matching_sections)} sections that look like the opener video."
        )
    sec = matching_sections[0]
    if len(sec.items) != 1:
        raise ValueError(f"The opener video section has {len(sec.items)} items.")
    return sec.items[0].title


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


def _get_announcements_video(
    items: List[PlanItem], messenger: Messenger
) -> Optional[str]:
    matches = [
        i for i in items if re.search("video announcements", i.title, re.IGNORECASE)
    ]
    if len(matches) == 0:
        messenger.log_problem(ProblemLevel.WARN, "No announcements video found.")
        return None
    elif len(matches) == 1:
        return matches[0].title
    else:
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Found {len(matches)} items that look like the announcements video",
        )
        return None


def _get_message_section(sections: List[PlanSection]) -> PlanSection:
    matching_sections = [s for s in sections if s.title.lower() == "message"]
    if len(matching_sections) != 1:
        raise ValueError(
            f"Found {len(matching_sections)} sections that look like the message."
        )
    return matching_sections[0]


def _get_bumper_video(sec: PlanSection) -> str:
    matches = [i for i in sec.items if re.search("bumper", i.title, re.IGNORECASE)]
    if len(matches) != 1:
        raise ValueError(f"Found {len(matches)} items that look like the bumper video.")
    name = matches[0].title
    prefix = "bumper video: "
    if name.lower().startswith(prefix):
        name = name[len(prefix) :]
    return name


def _get_message_notes(sec: PlanSection) -> str:
    matches = [
        i for i in sec.items if re.search("message title:", i.title, re.IGNORECASE)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Found {len(matches)} items that look like the message matches."
        )
    return matches[0].description.strip()


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
    opener_video = _get_opener_video(sections)
    announcements = _get_announcements(items, messenger)
    announcements_video = _get_announcements_video(items, messenger)
    msg_sec = _get_message_section(sections)
    bumper_video = _get_bumper_video(msg_sec)
    message_notes = _get_message_notes(msg_sec)
    songs = _get_songs(sections, messenger)
    return PlanItemsSummary(
        plan=plan,
        walk_in_slides=walk_in_slides,
        opener_video=opener_video,
        announcements=announcements,
        songs=songs,
        bumper_video=bumper_video,
        announcements_video=announcements_video,
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
        items = "\n".join([f"<li>{html.escape(s)}</li>" for s in self.slides])
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
        items = "\n".join([f"<li>{html.escape(s)}</li>" for s in self.slides])
        return f"""
<div class="{_SUPERHEADER_CLS}">Announcements</div>
<ul>
{_indent(items, 1)}
</ul>
""".strip()


@dataclass
class VideosSection:
    opener: Optional[str]
    bumper: Optional[str]
    announcements: Optional[str]

    def to_html(self) -> str:
        rows = (
            ([["Opener", html.escape(self.opener)]] if self.opener is not None else [])
            + (
                [["Bumper", html.escape(self.bumper)]]
                if self.bumper is not None
                else []
            )
            + (
                [["Announcements", html.escape(self.announcements)]]
                if self.announcements is not None
                else []
            )
        )
        tab = HtmlTable(cls=_VIDEO_TAB_CLS, ncols=2, header=None, rows=rows)
        return f"""
<div class="{_SUPERHEADER_CLS}">Videos</div>
{tab.to_html()}
""".strip()


@dataclass
class SongSection:
    songs: List[AnnotatedSong]

    def _make_row(self, s: AnnotatedSong) -> List[str]:
        # TODO: Line breaks aren't being represented properly here
        notes = [
            f"<span class='{_NOTES_TITLE_CLS}'>⚠️ {html.escape(n.category)}</span><br>{html.escape(n.contents)}"
            for n in s.notes
            if n.category == "Visuals"
        ]
        notes = "\n".join(notes)
        return [
            html.escape(s.song.ccli or ""),
            notes,
            html.escape(s.song.title or ""),
            html.escape(s.song.author or ""),
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
    notes: str

    def to_html(self) -> str:
        # TODO: There's too much indentation here
        btn = '<button id="copy-btn" onclick="copyMessageNotes()">Copy</button><br><span id="copy-confirm" style="visibility: hidden;">Copied &check;</span>'
        notes = f"<details><summary>Show notes</summary><pre id='message-notes'>{html.escape(self.notes)}</pre></details>"
        row = [
            f"<div class='{_EVEN_ROW_CLS}'>{btn}</div>",
            f"<div class='{_EVEN_ROW_CLS}'>{notes}</div>",
        ]
        tab = HtmlTable(cls=_MESSAGE_TAB_CLS, ncols=2, header=None, rows=[row])
        return f"""
<div class='{_SUPERHEADER_CLS}'>Message</div>
{tab.to_html()}
""".strip()


def plan_summary_to_html(summary: PlanItemsSummary) -> str:
    # TODO: Also warn the user if there are extra notes other than the ones for songs?
    title = (
        html.escape(f"{summary.plan.series_title}: {summary.plan.title}")
        if summary.plan.series_title
        else html.escape(summary.plan.title)
    )
    subtitle = html.escape(summary.plan.date.strftime("%B %d, %Y"))
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
                grid-template-columns: 7.5em 30em 1fr;
                border: 2px solid var(--dark-background-color);
                border-top: 0;
            }}
            .{_VIDEO_TAB_CLS} {{
                display: grid;
                grid-template-columns: 15em 1fr;
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
{message_section.to_html()}
        </div>
    </body>
</html>
""".lstrip()
