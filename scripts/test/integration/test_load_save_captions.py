import unittest
from pathlib import Path

import captions

_CAPTIONS_DIR = Path(__file__).parent.joinpath("captions_data")
_TEMP_DIR = Path(__file__).parent.joinpath("captions_temp")


class LoadSaveCaptionsTestCase(unittest.TestCase):
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
