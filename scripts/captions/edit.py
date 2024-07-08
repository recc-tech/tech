"""
Functions for editing captions (e.g., filtering out worship captions).
"""

import re
import statistics
from enum import Enum, auto
from typing import Dict, List, Set

from .cue import Cue


class Filter(Enum):
    SIMPLE_LEN = auto()
    SIMPLE_DELAY = auto()


def remove_worship_captions(
    vtt: List[Cue], filter: Filter = Filter.SIMPLE_LEN
) -> List[Cue]:
    match filter:
        case Filter.SIMPLE_LEN:
            f = _indices_to_remove_by_len
        case Filter.SIMPLE_DELAY:
            f = _indices_to_remove_by_time_diff
    indices_to_remove = f(vtt)
    cues_to_keep: List[Cue] = [
        c for (i, c) in enumerate(vtt) if i not in indices_to_remove
    ]
    return cues_to_keep


def _indices_to_remove_by_len(cues: List[Cue]) -> Set[int]:
    cue_lengths = [len(c.text) for c in cues]
    N = 2
    indices_with_running_avg = range(N, len(cue_lengths) - N - 1)
    running_avg_lens = {
        i: statistics.mean(cue_lengths[i - N : i + N + 1])
        for i in indices_with_running_avg
    }
    # We expect the cue lengths to follow a bimodal distribution. Try to base
    # the limit on the average of only the cues that we'll keep
    avg_cue_len = statistics.mean(cue_lengths)
    limit = 0.35 * statistics.mean([x for x in cue_lengths if x > avg_cue_len])
    return {i for i in indices_with_running_avg if running_avg_lens[i] < limit}


def _indices_to_remove_by_time_diff(cues: List[Cue]) -> Set[int]:
    MAX_TIME_DIFF = 5.0
    time_diff = [
        cues[i + 1].start.total_seconds() - cues[i].end.total_seconds()
        for i in range(len(cues) - 1)
    ]
    return {
        i
        for i in range(1, len(cues) - 1)
        if time_diff[i] > MAX_TIME_DIFF and time_diff[i - 1] > MAX_TIME_DIFF
    }


def apply_substitutions(cues: List[Cue], substitutions: Dict[str, str]) -> List[Cue]:
    r"""
    Edit the given captions using a simple search-and-replace approach.

    ## Examples

    >>> from datetime import timedelta
    >>> t0, t1, t2, t3, t4, t5 = (timedelta(seconds=n) for n in range(6))
    >>> cues = [
    ...     Cue(id="1", start=t0, end=t1, text="Welcome to river's", confidence=1.0),
    ...     Cue(id="2", start=t1, end=t2, text="edge!", confidence=0.0),
    ...     Cue(id="3", start=t2, end=t3, text="jesus is alive!", confidence=0.5),
    ...     Cue(id="4", start=t3, end=t4, text="river's edge.", confidence=1.0),
    ...     Cue(id="5", start=t4, end=t5, text='"mary\'s" should change, but not "primary".', confidence=1.0),
    ... ]
    >>> for c in apply_substitutions(cues, {"jesus": "Jesus", "river's edge": "River's Edge", "mary": "Mary"}):
    ...     print(c)
    Cue(id='1', start=datetime.timedelta(0), end=datetime.timedelta(seconds=1), text="Welcome to River's", confidence=1.0)
    Cue(id='2', start=datetime.timedelta(seconds=1), end=datetime.timedelta(seconds=2), text='Edge!', confidence=0.0)
    Cue(id='3', start=datetime.timedelta(seconds=2), end=datetime.timedelta(seconds=3), text='Jesus is alive!', confidence=0.5)
    Cue(id='4', start=datetime.timedelta(seconds=3), end=datetime.timedelta(seconds=4), text="River's Edge.", confidence=1.0)
    Cue(id='5', start=datetime.timedelta(seconds=4), end=datetime.timedelta(seconds=5), text='"Mary\'s" should change, but not "primary".', confidence=1.0)

    This function doesn't mutate the input list.

    >>> for c in cues:
    ...     print(c)
    Cue(id='1', start=datetime.timedelta(0), end=datetime.timedelta(seconds=1), text="Welcome to river's", confidence=1.0)
    Cue(id='2', start=datetime.timedelta(seconds=1), end=datetime.timedelta(seconds=2), text='edge!', confidence=0.0)
    Cue(id='3', start=datetime.timedelta(seconds=2), end=datetime.timedelta(seconds=3), text='jesus is alive!', confidence=0.5)
    Cue(id='4', start=datetime.timedelta(seconds=3), end=datetime.timedelta(seconds=4), text="river's edge.", confidence=1.0)
    Cue(id='5', start=datetime.timedelta(seconds=4), end=datetime.timedelta(seconds=5), text='"mary\'s" should change, but not "primary".', confidence=1.0)
    """
    # Don't mutate the input
    cues = list(cues)
    for old, new in substitutions.items():
        old_words = _split_words(old)
        new_words = _split_words(new)
        if len(old_words) != len(new_words):
            raise ValueError(f"'{old}' has a different number of words than '{new}'.")
        for i in range(len(cues)):
            j = i + 1
            while j <= len(cues) and 1 + _count_words(cues[i + 1 : j]) < len(old_words):
                j += 1
            j = min(len(cues), j)
            if _count_words(cues[i:j]) < len(old_words):
                break
            pattern = r"\s+".join([f"\\b{re.escape(w)}\\b" for w in old_words])
            repl = " ".join(new_words)
            string = " ".join([c.text for c in cues[i:j]])
            updated_text = re.sub(pattern=pattern, repl=repl, string=string)
            updated_words = _split_words(updated_text)
            for k in range(i, j):
                n = len(_split_words(cues[k].text))
                cues[k] = cues[k].with_text(" ".join(updated_words[:n]))
                updated_words = updated_words[n:]
    return cues


def _split_words(phrase: str) -> List[str]:
    return [x.strip() for x in re.split(r"\s+", phrase) if x.strip()]


def _count_words(cues: List[Cue]) -> int:
    lines = [c.text for c in cues]
    return len(_split_words(" ".join(lines)))
