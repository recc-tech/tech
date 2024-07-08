import unittest
from pathlib import Path

import captions
from args import ReccArgs
from config import Config

_CAPTIONS_DIR = Path(__file__).parent.joinpath("captions_data")
_TEMP_DIR = Path(__file__).parent.joinpath("captions_temp")


class ApplySubstitutionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _TEMP_DIR.mkdir(exist_ok=True)

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
