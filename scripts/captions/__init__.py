import statistics
from typing import List, Set

from webvtt.structures import Caption
from webvtt.webvtt import WebVTT

# TODO: Also spell check (or at least apply the substitutions in substitutions.csv)


def remove_worship_captions(vtt: WebVTT) -> WebVTT:
    indices_to_remove = _indices_to_remove_by_len(vtt.captions)
    cues_to_keep: List[Caption] = [
        c for (i, c) in enumerate(vtt.captions) if i not in indices_to_remove
    ]
    return WebVTT(captions=cues_to_keep)


def _indices_to_remove_by_len(  # pyright: ignore[reportUnusedFunction]
    cues: List[Caption],
) -> Set[int]:
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


def _indices_to_remove_by_time_diff(  # pyright: ignore[reportUnusedFunction]
    cues: List[Caption],
) -> Set[int]:
    MAX_TIME_DIFF = 5.0
    time_diff = [
        cues[i + 1].start_in_seconds - cues[i].end_in_seconds
        for i in range(len(cues) - 1)
    ]
    return {
        i
        for i in range(1, len(cues) - 1)
        if time_diff[i] > MAX_TIME_DIFF and time_diff[i - 1] > MAX_TIME_DIFF
    }
