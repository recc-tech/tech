# pyright: basic

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
    was_removed = {i: i not in final_ids for i in original_ids}

    time_diff = [
        original_vtt[i + 1].start_in_seconds - original_vtt[i].end_in_seconds
        for i in range(len(original_vtt) - 1)
    ]

    fig, ax = plt.subplots()
    ax.bar(
        list(range(len(original_vtt) - 1)),
        time_diff,
        color=["red" if was_removed[i] else "blue" for i in original_ids],
        width=1.0,
    )
    ax.set_xticks([])

    plt.show()


if __name__ == "__main__":
    main()
