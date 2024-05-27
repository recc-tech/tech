import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import webvtt

PAST_CAPTIONS_DIR = Path(__file__).resolve().parent.parent.joinpath("captions_data")


def main():
    dir = PAST_CAPTIONS_DIR.joinpath(sys.argv[1])
    original_vtt = webvtt.read(dir.joinpath("original.vtt"))
    original_ids = [c.identifier for c in original_vtt]
    final_vtt = webvtt.read(dir.joinpath("final.vtt"))
    final_ids = [c.identifier for c in final_vtt]
    was_removed_manually = {i: i not in final_ids for i in original_ids}

    cue_lengths = [len(c.text) for c in original_vtt]

    # Copied from captions/__init__.py package
    N = 1
    indices_with_running_avg = range(N, len(cue_lengths) - N - 1)
    running_avg_lens = {
        i: statistics.mean(cue_lengths[i - N : i + N + 1])
        for i in indices_with_running_avg
    }
    avg_cue_len = statistics.mean(cue_lengths)
    limit = 0.35 * statistics.mean([x for x in cue_lengths if x > avg_cue_len])
    was_removed_automatically = {
        original_vtt[i].identifier: i in indices_with_running_avg
        and running_avg_lens[i] < limit
        for i in range(len(original_vtt))
    }

    fig, (ax0, ax1) = plt.subplots(nrows=2, ncols=1)

    ax0.bar(
        list(range(len(original_vtt))),
        cue_lengths,
        color=[
            (
                "green"
                if was_removed_manually[i] == was_removed_automatically[i]
                else (
                    "red"
                    if was_removed_automatically[i] and not was_removed_manually[i]
                    else "purple"
                )
            )
            for i in original_ids
        ],
        width=1.0,
    )
    ax0.plot(list(range(len(original_vtt))), [avg_cue_len for _ in original_vtt])
    ax0.plot(indices_with_running_avg, running_avg_lens.values())
    ax0.set_xticks(
        ticks=list(range(len(original_vtt))),
        labels=[c.start for c in original_vtt],
        rotation=90,
    )
    ax0.set_title("Cue lengths over time")

    ax1.hist(cue_lengths, bins=50)
    ax1.set_title("Distribution of cue lengths")

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
