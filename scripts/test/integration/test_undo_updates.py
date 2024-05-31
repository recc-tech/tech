import os
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import List

GIT_REPO_URL = "https://github.com/recc-tech/tech.git"
OUTER_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTER_UNDO_UPDATES_SCRIPT = OUTER_REPO_ROOT.joinpath("scripts", "undo_updates.command")
INNER_REPO_ROOT = Path(__file__).resolve().parent.joinpath("repo_copy")
INNER_UNDO_UPDATES_SCRIPT = INNER_REPO_ROOT.joinpath("scripts", "undo_updates.command")

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RESET_COLOR = "\033[0m"


class UndoUpdatesTestCase(unittest.TestCase):
    """
    Test the undo_updates.command script, mostly so that I can test on macOS
    via GitHub Actions before actually "deploying" the script.
    """

    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(INNER_REPO_ROOT, ignore_errors=True)
        # Test on a copy of the repo because checking out random commits in the
        # current repo while running tests would be very wonky.
        subprocess.run(["git", "clone", GIT_REPO_URL, INNER_REPO_ROOT])
        os.chdir(INNER_REPO_ROOT)
        cls.avail_tags = sorted(_get_tags(), reverse=True)[:5]

    def setUp(self) -> None:
        shutil.copy(src=OUTER_UNDO_UPDATES_SCRIPT, dst=INNER_UNDO_UPDATES_SCRIPT)

    def test_rollback_to_latest(self) -> None:
        result = subprocess.run(
            [INNER_UNDO_UPDATES_SCRIPT.as_posix()],
            input="latest\n\n",
            encoding="ascii",
            capture_output=True,
        )
        tag_list = "\n".join([f" * {t}" for t in self.avail_tags])
        expected = f"""AVAILABLE VERSIONS:
 * latest
{tag_list}

SELECT THE VERSION TO USE:
> {GREEN}OK: currently on the latest version.{RESET_COLOR}
Press ENTER to exit..."""
        self.assertEqual(0, result.returncode)
        self.assertEqual(expected, result.stdout)
        self.assertEqual("", result.stderr)

    def test_rollback_to_second_latest(self) -> None:
        tag = self.avail_tags[1]
        result = subprocess.run(
            [INNER_UNDO_UPDATES_SCRIPT.as_posix()],
            input=f"{tag}\n\n",
            encoding="ascii",
            capture_output=True,
        )
        tag_list = "\n".join([f" * {t}" for t in self.avail_tags])
        expected = f"""AVAILABLE VERSIONS:
 * latest
{tag_list}

SELECT THE VERSION TO USE:
> {GREEN}OK: currently on version {tag}.{RESET_COLOR}
Press ENTER to exit..."""
        self.assertEqual(0, result.returncode)
        self.assertEqual(expected, result.stdout)
        self.assertEqual("", result.stderr)

    def test_rollback_to_invalid(self) -> None:
        result = subprocess.run(
            [INNER_UNDO_UPDATES_SCRIPT.as_posix()],
            input=f"\n\n",
            encoding="ascii",
            capture_output=True,
        )
        tag_list = "\n".join([f" * {t}" for t in self.avail_tags])
        expected = f"""AVAILABLE VERSIONS:
 * latest
{tag_list}

SELECT THE VERSION TO USE:
> {RED}Failed to switch to the selected version. Are you sure you selected a valid one?{RESET_COLOR}
{YELLOW}error: pathspec 'tags/' did not match any file(s) known to git{RESET_COLOR}
Press ENTER to exit..."""
        self.assertEqual(0, result.returncode)
        self.assertEqual(expected, result.stdout)
        self.assertEqual("", result.stderr)


def _get_tags() -> List[str]:
    result = subprocess.run(
        ["git", "tag", "--list"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    out = result.stdout
    return [l for l in out.split("\n") if l]
