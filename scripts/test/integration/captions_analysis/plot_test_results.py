import json
from pathlib import Path

import matplotlib.pyplot as plt

STATS_FILE = Path(__file__).parent.joinpath("worship_caption_removal_stats.json")


def main():
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        stats = json.load(f)
    weeks = sorted(stats["missing"].keys())

    fig, (ax0, ax1) = plt.subplots(nrows=2, ncols=1)

    # Missing
    missing = [stats["missing"][w] for w in weeks]
    ax0.bar(weeks, missing)
    ax0.set_xticks(ticks=weeks, labels=weeks, rotation=90)
    ax0.set_title("Missing cues")

    # Leftover
    leftover = [stats["leftover"][w] for w in weeks]
    ax1.bar(weeks, leftover)
    ax1.set_xticks(ticks=weeks, labels=weeks, rotation=90)
    ax1.set_title("Leftover cues")

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
