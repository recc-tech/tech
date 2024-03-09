import typing
import unittest
from pathlib import Path

from args import ReccArgs


class ReccArgsTestCase(unittest.TestCase):
    def test_repo_root(self) -> None:
        args = ReccArgs.parse([])
        root = args.get("REPO_ROOT")
        self.assertIsInstance(root, str)
        root = Path(typing.cast(str, root))
        self.assertTrue(root.is_dir(), "Repository root should exist.")
        # Check that root isn't pointing to the wrong directory
        self.assertTrue(
            root.joinpath(".github", "workflows"),
            "Repository root must contain the .github/workflows directory.",
        )

    def test_startup_ymd(self) -> None:
        self.assertEqual(
            "2024-03-08",
            ReccArgs.parse(["", "--date", "2024-03-08"]).get("STARTUP_YMD"),
        )

    def test_startup_mdy(self) -> None:
        self.assertEqual(
            "March 8, 2024",
            ReccArgs.parse(["", "--date", "2024-03-08"]).get("STARTUP_MDY"),
        )
