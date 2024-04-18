from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from typing import List, TypeVar

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
    ]
    if len(matches) != 4:
        titles = [i.title for i in matches]
        messenger.log_problem(
            ProblemLevel.WARN,
            f"Found {len(matches)} items that look like lists of announcements: {', '.join(titles)}.",
        )
    slide_names: List[str] = []
    for itm in matches:
        if re.search("video announcements", itm.title, re.IGNORECASE):
            slide_names = _merge(slide_names, [itm.title])
        else:
            names = _get_announcement_slide_names(itm)
            slide_names = _merge(slide_names, names)
    return slide_names


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
        message_notes=message_notes,
    )


def _make_song_tr(s: AnnotatedSong) -> str:
    notes_html_list: List[str] = []
    for n in s.notes:
        notes_html_list.append(
            f"<span class='notes-title'>⚠️ {n.category}</span><br>{n.contents}"
        )
    notes = "<br>".join(notes_html_list)
    return f"""
<tr>
    <td>{s.song.ccli or ''}</td>
    <td class='extra-info'>{s.song.title or ''}</td>
    <td class='extra-info'>{s.song.author or ''}</td>
    <td>{notes}</td>
</tr>
""".strip()


def _indent(code: str, indent: str) -> str:
    return "\n".join([f"{indent}{c}" for c in code.split("\n")])


def _make_songs_table(songs: List[AnnotatedSong]) -> str:
    trs = [_make_song_tr(s) for s in songs]
    trs = "\n".join([_indent(t, "        ") for t in trs])
    return f"""
<table>
    <tbody>
        <tr>
            <th>CCLI</th>
            <th class='extra-info'>Title</th>
            <th class='extra-info'>Author</th>
            <th>Notes</th>
        </tr>
{trs}
    </tbody>
</table>
""".strip()


def plan_summary_to_html(summary: PlanItemsSummary) -> str:
    title = (
        html.escape(f"{summary.plan.series_title}: {summary.plan.title}")
        if summary.plan.series_title
        else html.escape(summary.plan.title)
    )
    subtitle = html.escape(summary.plan.date.strftime("%B %d, %Y"))
    walk_in_slide_bullets = [
        f"<li>{html.escape(s)}</li>" for s in summary.walk_in_slides
    ]
    walk_in_slides = f"<ul>{''.join(walk_in_slide_bullets)}</ul>"
    opener_video = html.escape(summary.opener_video)
    announcement_bullets = [f"<li>{html.escape(a)}</li>" for a in summary.announcements]
    announcements = f"<ul>{''.join(announcement_bullets)}</ul>"
    songs_table = _make_songs_table(summary.songs)
    bumper_video = html.escape(summary.bumper_video)
    message_notes = html.escape(summary.message_notes)
    message_notes_btn = (
        '<button onclick="copyMessageNotes()">Copy</button>'
        if message_notes
        else '<span class="missing">[[None]]</span>'
    )
    # TODO: Also warn the user if there are extra notes other than the ones for songs?
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
                background-color: #fafafa;
            }}
            body {{
                margin: 0;
            }}
            header {{
                /* Same as the website */
                background-color: #1a7ee5;
                color: white;
                padding: 1em;
            }}
            #main-content {{
                margin: 1em 1em 5em 1em;
            }}
            h1 {{
                font-size: x-large;
            }}
            h2 {{
                font-size: large;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid black;
                padding: 0.25em;
                margin: 0;
                vertical-align: top;
            }}
            .extra-info {{
                color: grey;
            }}
            .missing {{
                color: red;
            }}
            .notes-title {{
                font-weight: bolder;
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
            <h2>Walk-In Slides</h2>
            {walk_in_slides}
            <h2>Opener Video</h2>
            {opener_video}
            <h2>Announcements</h2>
            {announcements}
            <h2>Songs</h2>
            {songs_table}
            <h2>Bumper Video</h2>
            {bumper_video}
            <h2>Message Notes</h2>
            {message_notes_btn}
            <span id="copy-confirm" style="visibility: hidden;">Copied &check;</span>
            <details class="extra-info">
                <summary>Show notes</summary>
                <pre id="message-notes">{message_notes}</pre>
            </details>
        </div>
    </body>
</html>
""".lstrip()
