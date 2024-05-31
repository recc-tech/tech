import os
import platform
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import List

GIT_REPO_URL = "https://github.com/recc-tech/tech.git"
OUTER_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTER_UNDO_UPDATES_NIX = OUTER_REPO_ROOT.joinpath("scripts", "undo_updates.command")
OUTER_UNDO_UPDATES_WINDOWS = OUTER_REPO_ROOT.joinpath("scripts", "undo_updates.bat")
OUTER_UNDO_UPDATES_PY = OUTER_REPO_ROOT.joinpath("scripts", "undo_updates.py")
INNER_REPO_ROOT = Path(__file__).resolve().parent.joinpath("repo_copy")
INNER_UNDO_UPDATES_NIX = INNER_REPO_ROOT.joinpath("scripts", "undo_updates.command")
INNER_UNDO_UPDATES_WINDOWS = INNER_REPO_ROOT.joinpath("scripts", "undo_updates.bat")
INNER_UNDO_UPDATES_PY = INNER_REPO_ROOT.joinpath("scripts", "undo_updates.py")

RED = "\033[0;31m"
GREEN = "\033[0;32m"
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
        subprocess.run(
            ["git", "clone", GIT_REPO_URL, INNER_REPO_ROOT],
            check=True,
            capture_output=True,
        )
        cls.avail_tags = sorted(_get_tags(), reverse=True)[:5]
        cls.maxDiff = None
        cls.original_cwd = os.getcwd()
        os.chdir(INNER_REPO_ROOT)

    @classmethod
    def tearDownClass(cls) -> None:
        os.chdir(cls.original_cwd)
        shutil.rmtree(INNER_REPO_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        current_os = platform.system().lower().strip()
        if current_os in {"macos", "linux"}:
            self.outer_undo_updates_script = OUTER_UNDO_UPDATES_NIX
            self.inner_undo_updates_script = INNER_UNDO_UPDATES_NIX
        elif current_os == "windows":
            self.outer_undo_updates_script = OUTER_UNDO_UPDATES_WINDOWS
            self.inner_undo_updates_script = INNER_UNDO_UPDATES_WINDOWS
        else:
            self.fail(f"Operating system '{current_os}' is not supported.")
        shutil.copy(
            src=self.outer_undo_updates_script, dst=self.inner_undo_updates_script
        )
        shutil.copy(src=OUTER_UNDO_UPDATES_PY, dst=INNER_UNDO_UPDATES_PY)

    def test_rollback_to_latest(self) -> None:
        result = subprocess.run(
            [self.inner_undo_updates_script.as_posix()],
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
            [self.inner_undo_updates_script.as_posix()],
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
            [self.inner_undo_updates_script.as_posix()],
            input=f"\n\n",
            encoding="ascii",
            capture_output=True,
        )
        tag_list = "\n".join([f" * {t}" for t in self.avail_tags])
        expected_stdout = f"""AVAILABLE VERSIONS:
 * latest
{tag_list}

SELECT THE VERSION TO USE:
> Press ENTER to exit..."""
        expected_stderr = f"{RED}Invalid choice.{RESET_COLOR}\n"
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(expected_stdout, result.stdout)
        self.assertEqual(expected_stderr, result.stderr)


def _get_tags() -> List[str]:
    result = subprocess.run(
        ["git", "tag", "--list"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    out = result.stdout
    return [l for l in out.split("\n") if l]
