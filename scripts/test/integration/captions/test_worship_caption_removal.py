import json
import os
import unittest
from pathlib import Path
from typing import Dict

import webvtt
from captions import remove_worship_captions

PAST_CAPTIONS_DIR = Path(__file__).parent.joinpath("past_captions")
STATS_FILE = Path(__file__).parent.joinpath("worship_caption_removal_stats.json")
# TODO: Adjust these
MAX_MISSING = 8
MAX_LEFTOVER_RATE = 0.6

class WorshipCaptionRemovalTestCase(unittest.TestCase):
    def test(self):
        weekly_dirs = {
            Path(f.path) for f in os.scandir(PAST_CAPTIONS_DIR) if f.is_dir()
        }
        missing_by_week: Dict[str, int] = {}
        leftover_rate_by_week: Dict[str, float] = {}
        for subdir in weekly_dirs:
            week = subdir.stem
            if week == "2022-06-19":
                self.skipTest("This week seems to be an outlier in terms of leftover rate.")
            if week >= "2023-11-26":
                self.skipTest("This week is after 2022-11-26, so its caption removal was likely done automatically.")
            with self.subTest(week):
                original_captions = webvtt.read(subdir.joinpath("original.vtt"))
                expected_final_captions = webvtt.read(subdir.joinpath("final.vtt"))
                num_cues_to_remove = len(original_captions) - len(
                    expected_final_captions
                )
                # TODO: Remove worship captions from original and compare with final
                actual_final_captions = remove_worship_captions(original_captions)
                actual_caption_ids = [c.identifier for c in actual_final_captions]
                expected_caption_ids = [c.identifier for c in expected_final_captions]
                num_missing_cues = len(
                    [c for c in expected_caption_ids if c not in actual_caption_ids]
                )
                num_leftover_cues = len(
                    [c for c in actual_caption_ids if c not in expected_caption_ids]
                )
                missing_by_week[week] = num_missing_cues
                leftover_rate_by_week[week] = num_leftover_cues / num_cues_to_remove
                self.assertLessEqual(
                    missing_by_week[week],
                    MAX_MISSING,
                    f"No more than {MAX_MISSING} non-worship captions should be removed.",
                )
                self.assertLessEqual(
                    leftover_rate_by_week[week],
                    MAX_LEFTOVER_RATE,
                    f"No more than {100 * MAX_LEFTOVER_RATE}% of worship captions should be left.",
                )
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            output = {"missing": missing_by_week, "leftover": leftover_rate_by_week}
            json.dump(output, f, indent=2)
