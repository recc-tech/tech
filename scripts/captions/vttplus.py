"""
Functions for converting to and from a subset of the WebVTT format that
includes confidence values.
"""

import re
import warnings
from datetime import timedelta
from pathlib import Path
from typing import Iterable, Iterator, Optional, Tuple

from .cue import Cue


def save(cues: Iterable[Cue], p: Path) -> None:
    p.parent.mkdir(exist_ok=True, parents=True)
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(serialize(cues))


def load(p: Path) -> Iterator[Cue]:
    return parse(p.read_text(encoding="utf-8"))


def serialize(cues: Iterable[Cue]) -> Iterator[str]:
    """
    Convert the given cues to a string in WebVTT format.

    ## Examples

    >>> txt = serialize([])
    >>> print("".join(txt))
    WEBVTT
    <BLANKLINE>
    <BLANKLINE>

    >>> txt = serialize([
    ...   Cue(id="1", start=timedelta(seconds=0), end=timedelta(minutes=1, seconds=1, milliseconds=42), text="Hello there!", confidence=None),
    ...   Cue(id="2", start=timedelta(minutes=1, seconds=30, milliseconds=99), end=timedelta(hours=1, minutes=59, seconds=59, milliseconds=432), text="General Kenobi!", confidence=0.432)
    ... ])
    >>> print("".join(txt))
    WEBVTT
    <BLANKLINE>
    1
    00:00:00.000 --> 00:01:01.042
    Hello there!
    <BLANKLINE>
    NOTE confidence=0.432
    <BLANKLINE>
    2
    00:01:30.099 --> 01:59:59.432
    General Kenobi!
    <BLANKLINE>
    <BLANKLINE>
    """
    # TODO: Add some validation (e.g., end time must be after start time for each cue, cue text can't contain newlines, etc.)?
    yield "WEBVTT\n\n"
    for c in cues:
        if c.confidence is not None:
            yield f"NOTE confidence={c.confidence}\n\n"
        yield f"{c.id}\n"
        yield f"{_format_timedelta(c.start)} --> {_format_timedelta(c.end)}\n"
        yield f"{c.text}\n\n"


def parse(vtt: str) -> Iterator[Cue]:
    r"""
    Parse a string in WebVTT format to a list of cues.

    >>> list(parse("WEBVTT\n\n"))
    []

    Normally, all cues should be preceded by a comment with the confidence.

    >>> vtt = '''WEBVTT
    ...
    ... NOTE confidence=0.0
    ...
    ... 12
    ... 01:02:03.456 --> 01:03:04.567
    ... Hello there!
    ...
    ... NOTE confidence=0.42
    ...
    ... 14
    ... 02:03:04.123 --> 04:11:45.987
    ... Here is another cue.
    ...
    ... '''
    >>> for c in parse(vtt):
    ...     print(c)
    Cue(id='12', start=datetime.timedelta(seconds=3723, microseconds=456000), end=datetime.timedelta(seconds=3784, microseconds=567000), text='Hello there!', confidence=0.0)
    Cue(id='14', start=datetime.timedelta(seconds=7384, microseconds=123000), end=datetime.timedelta(seconds=15105, microseconds=987000), text='Here is another cue.', confidence=0.42)

    However, this function also handles the case where no cues have confidence
    values.
    This is useful for parsing old .vtt files downloaded from BoxCast, which do
    not have the confidence values at all.

    >>> vtt = '''WEBVTT
    ...
    ... NOTE This is just a random comment, not a confidence value
    ...
    ... 42
    ... 00:00:00.000 --> 00:00:01.000
    ... First cue (no confidence)
    ...
    ... 43
    ... 00:00:01.000 --> 00:00:02.000
    ... Second cue (no confidence)
    ...
    ... '''
    >>> for c in parse(vtt):
    ...     print(c)
    Cue(id='42', start=datetime.timedelta(0), end=datetime.timedelta(seconds=1), text='First cue (no confidence)', confidence=None)
    Cue(id='43', start=datetime.timedelta(seconds=1), end=datetime.timedelta(seconds=2), text='Second cue (no confidence)', confidence=None)

    Likewise, it may be the case that *some* (but not all) cues have a
    confidence value.
    For example, the user may edit the captions and accidentally delete a
    comment.
    The user may also delete a cue without deleting the associated confidence
    value.
    Therefore, if there are multiple confidence values in a row, only the last
    one counts.

    >>> vtt = '''WEBVTT
    ...
    ... 99
    ... 00:00:01.000 --> 00:00:02.000
    ... Cue 1
    ...
    ... NOTE confidence=0.41
    ...
    ... NOTE confidence=0.42
    ...
    ... 100
    ... 00:00:02.000 --> 00:00:03.000
    ... Cue 2
    ...
    ... '''
    >>> for c in parse(vtt):
    ...     print(c)
    Cue(id='99', start=datetime.timedelta(seconds=1), end=datetime.timedelta(seconds=2), text='Cue 1', confidence=None)
    Cue(id='100', start=datetime.timedelta(seconds=2), end=datetime.timedelta(seconds=3), text='Cue 2', confidence=0.42)

    """
    # TODO: Test what happens when there's early EOF
    blocks = [blk.strip() for blk in vtt.split("\n\n") if blk.strip()]
    if blocks[0] != "WEBVTT":
        raise ValueError("Missing WEBVTT at beginning of file.")
    current_confidence: Optional[float] = None
    for blk in blocks[1:]:
        if blk.startswith("NOTE confidence="):
            confidence_str = blk[16:]
            try:
                current_confidence = float(confidence_str)
            except ValueError:
                warnings.warn(f"Failed to parse confidence value {confidence_str}")
                current_confidence = None
        elif blk.startswith("NOTE "):
            pass
        else:
            lines = blk.split("\n")
            if len(lines) != 3:
                cue_id = f" (cue ID: {lines[0].strip()})" if len(lines) > 0 else ""
                raise ValueError(
                    f"Wrong number of lines in a cue{cue_id}. Expected exactly 3, but found {len(lines)}"
                )
            start, end = _parse_time_range(lines[1])
            yield Cue(
                id=lines[0].strip(),
                start=start,
                end=end,
                text=lines[2].strip(),
                confidence=current_confidence,
            )
            current_confidence = None


def _format_timedelta(td: timedelta) -> str:
    """
    Convert a timedelta to the format required for a .vtt file.

    ## Examples
    >>> _format_timedelta(timedelta(seconds=0))
    '00:00:00.000'

    >>> _format_timedelta(timedelta(seconds=3722, milliseconds=1_042))
    '01:02:03.042'
    """
    tot_seconds = int(td.total_seconds())
    seconds = tot_seconds % 60
    minutes = (tot_seconds // 60) % 60
    hours = tot_seconds // (60 * 60)
    millis = td.microseconds // 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _parse_time_range(text: str) -> Tuple[timedelta, timedelta]:
    """
    Parse a time range, as from a .vtt file.

    ## Examples
    >>> _parse_time_range("01:02:03.456 --> 59:58:57.009")
    (datetime.timedelta(seconds=3723, microseconds=456000), datetime.timedelta(days=2, seconds=43137, microseconds=9000))
    """
    part1, part2 = text.split("-->")
    m1 = re.fullmatch(r"(\d\d):(\d\d):(\d\d).(\d\d\d)", part1.strip())
    if m1 is None:
        raise ValueError("Invalid start time.")
    t1 = timedelta(
        hours=int(m1[1]),
        minutes=int(m1[2]),
        seconds=int(m1[3]),
        milliseconds=int(m1[4]),
    )
    m2 = re.fullmatch(r"(\d\d):(\d\d):(\d\d).(\d\d\d)", part2.strip())
    if m2 is None:
        raise ValueError("Invalid end time.")
    t2 = timedelta(
        hours=int(m2[1]),
        minutes=int(m2[2]),
        seconds=int(m2[3]),
        milliseconds=int(m2[4]),
    )
    return t1, t2
