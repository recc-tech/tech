"""
Functions for editing captions (e.g., filtering out worship captions).
"""

import statistics
from enum import Enum, auto
from typing import List, Set

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
