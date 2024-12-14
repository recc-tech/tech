import json
import os
import unittest
from pathlib import Path
from typing import Dict

import captions
from args import ReccArgs
from config import Config

_CAPTIONS_DIR = Path(__file__).parent.joinpath("captions_data")
_TEMP_DIR = Path(__file__).parent.joinpath("captions_temp")
# Worship caption removal
_WCR_STATS_FILE = Path(__file__).parent.joinpath(
    "captions_analysis", "worship_caption_removal_stats.json"
)
_WCR_MAX_MISSING = 8
_WCR_MAX_LEFTOVER_RATE = 0.6


class CaptionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _TEMP_DIR.mkdir(exist_ok=True)

    def test_load_and_save(self) -> None:
        # Test that, if you load a .vtt file and then save it again, the new
        # .vtt is identical to the old.
        # Assuming the function for loading captions is deterministic, this
        # also means that saving and then loading captions yields the same
        # captions in memory (if the function is deterministic and the new .vtt
        # file is identical to the old one, then the result will also be
        # identical).
        num_cases = 0
        for d in _CAPTIONS_DIR.iterdir():
            if not d.is_dir():
                continue
            for p in d.glob("*.vtt"):
                if not p.is_file():
                    continue
                with self.subTest(f"{d.name}/{p.name}"):
                    num_cases += 1
                    new_path = _TEMP_DIR.joinpath(d.name, p.name)
                    new_path.parent.mkdir(exist_ok=True)
                    captions.save(captions.load(p), new_path)
                    self.assertEqual(p.read_text(), new_path.read_text())
        # Sanity check in case the .vtt files are missing for some reason
        self.assertGreaterEqual(num_cases, 1)

    def test_apply_substitutions(self) -> None:
        config = Config(args=ReccArgs.parse([]), allow_multiple_only_for_testing=True)
        num_cases = 0
        for p in _CAPTIONS_DIR.glob("**/original.vtt"):
            if not p.is_file():
                continue
            with self.subTest(f"{p.parent.name}/{p.name}"):
                num_cases += 1
                new_path = _TEMP_DIR.joinpath(p.parent.name, "with_substitutions.vtt")
                new_path.parent.mkdir(exist_ok=True)
                expected_path = _CAPTIONS_DIR.joinpath(
                    p.parent.name, "with_substitutions.vtt"
                )
                new_captions = captions.apply_substitutions(
                    list(captions.load(p)),
                    config.caption_substitutions,
                )
                captions.save(new_captions, new_path)
                self.assertEqual(expected_path.read_text(), new_path.read_text())
        # Sanity check in case the .vtt files are missing for some reason
        self.assertGreaterEqual(num_cases, 1)

    def test_remove_worship_captions(self):
        weekly_dirs = {Path(f.path) for f in os.scandir(_CAPTIONS_DIR) if f.is_dir()}
        missing_by_week: Dict[str, int] = {}
        leftover_rate_by_week: Dict[str, float] = {}
        for subdir in weekly_dirs:
            week = subdir.stem
            with self.subTest(week):
                if week == "2022-06-19":
                    self.skipTest(
                        "The week of 2022-06-19 is an outlier in terms of leftover rate."
                    )
                if week > "2023-12-03":
                    self.skipTest(
                        "This date is on or after 2023-12-03, so its caption removal was likely done automatically."
                    )
                original_captions = list(captions.load(subdir.joinpath("original.vtt")))
                expected_final_captions = list(
                    captions.load(subdir.joinpath("final.vtt"))
                )
                num_cues_to_remove = len(original_captions) - len(
                    expected_final_captions
                )
                actual_final_captions = captions.remove_worship_captions(
                    original_captions
                )
                actual_caption_ids = [c.id for c in actual_final_captions]
                expected_caption_ids = [c.id for c in expected_final_captions]
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
                    _WCR_MAX_MISSING,
                    f"No more than {_WCR_MAX_MISSING} non-worship captions should be removed.",
                )
                self.assertLessEqual(
                    leftover_rate_by_week[week],
                    _WCR_MAX_LEFTOVER_RATE,
                    f"No more than {100 * _WCR_MAX_LEFTOVER_RATE}% of worship captions should be left.",
                )
        with open(_WCR_STATS_FILE, "w", encoding="utf-8") as f:
            output = {"missing": missing_by_week, "leftover": leftover_rate_by_week}
            json.dump(output, f, indent=2)
