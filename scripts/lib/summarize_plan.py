from __future__ import annotations

import html
import inspect
from dataclasses import dataclass
from datetime import date
from typing import List

from external_services import Plan, PlanningCenterClient, Song


@dataclass
class PlanItemsSummary:
    plan: Plan
    walk_in_slides: List[str]
    opener_video: str
    announcements: List[str]
    songs: List[Song]
    bumper_video: str
    message_notes: str


def get_plan_summary(client: PlanningCenterClient, dt: date) -> PlanItemsSummary:
    # Songs: https://api.planningcenteronline.com/services/v2/service_types/882857/plans/70722878/items?per_page=200&include=song
    plan = client.find_plan_by_date(dt)
    # TODO: Use this as a test
    return PlanItemsSummary(
        plan=plan,
        walk_in_slides=[
            "River’s Edge Community Church",
            "Belong Before You Believe",
            "The Way Of The Cross Series Title Slide",
            "Ways To Give",
            "The After party",
            "RE Website",
            "Follow Us Instagram",
        ],
        opener_video="Worship Intro Video",
        announcements=[
            "Thanks For Joining Us",
            "Belong Before You Believe",
            "Message Series - Title Slide",
            "AGM",
            "Cafe Volunteers",
            "Community Kitchen Brunch",
            "Pulse Retreat",
            "Community Hall Fundraiser",
            "4 Ways To Give",
            "Prayer Ministry",
            "Website",
            "After Party",
            "See You Next Sunday",
        ],
        songs=[
            Song(
                ccli="7138371",
                title="Everlasting Light",
                author="Bede Benjamin-Korporaal, Jessie Early, and Mariah Gross",
            ),
            Song(
                ccli="2456623",
                title="You Are My King (Amazing Love)",
                author="Billy Foote",
            ),
            Song(
                ccli="6454621",
                title="Victor's Crown",
                author="Israel Houghton, Kari Jobe, and Darlene Zschech",
            ),
            Song(ccli="6219086", title="Redeemed", author="Big Daddy Weave"),
        ],
        bumper_video="24 Hours That Changed Everything",
        message_notes=inspect.cleandoc(
            """
            Crowned
            Mark 14:61-65 NLT
            John 18:35-37 NLT
            A Twisted Truth
            John 19:2 NLT
            A Twisted Pain
            Proverbs 22:5 NLT
            A Twisted Crown
            Genesis 3:17-18 NLT
            A Twisted Curse
            Hebrews 12:2-3 NLT
            A Crowned King
            """
        ),
    )


def plan_summary_to_html(summary: PlanItemsSummary) -> str:
    title = html.escape(f"{summary.plan.series_title}: {summary.plan.title}")
    subtitle = html.escape(summary.plan.date.strftime("%B %d, %Y"))
    walk_in_slides = html.escape(", ".join(summary.walk_in_slides))
    opener_video = html.escape(summary.opener_video)
    announcements = html.escape(", ".join(summary.announcements))
    song_elems = [
        f"<span title='\"{html.escape(s.title)}\"&#010;by {html.escape(s.author)}' class='song'>{html.escape(s.ccli)}</span>"
        for s in summary.songs
    ]
    songs = ", ".join(song_elems)
    bumper_video = html.escape(summary.bumper_video)
    message_notes = html.escape(summary.message_notes)
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
            }}
            body {{
                margin: 0;
            }}
            #header {{
                /* Same as the website */
                background-color: #1a7ee5;
                color: white;
                padding: 0.5em;
            }}
            .song {{
                text-decoration: underline dotted 2px;
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
        <div id="header">
            <h1>{title}</h1>
            <h2>{subtitle}</h2>
        </div>
        <ul>
            <li><b>Walk-in slides:</b> {walk_in_slides}</li>
            <li><b>Opener video:</b> {opener_video}</li>
            <li><b>Announcements:</b> {announcements}</li>
            <li><b>Songs:</b> {songs}</li>
            <li><b>Bumper video:</b> {bumper_video}</li>
            <li>
                <b>Message notes:</b>
                <button onclick="copyMessageNotes()">Copy</button>
                <span id="copy-confirm" style="visibility: hidden;">Copied &check;</span>
                <details>
                    <summary>Show notes</summary>
                    <pre id="message-notes">{message_notes}</pre>
                </details>
            </li>
        </ul>
    </body>
</html>
"""
