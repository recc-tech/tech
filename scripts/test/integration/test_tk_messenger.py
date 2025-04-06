import os
import subprocess
import sys
import unittest
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent.parent
_DATA_DIR = Path(__file__).parent.joinpath("tk_messenger_data")


class TkMessengerTestCase(unittest.TestCase):
    def test_auto_close(self) -> None:
        python = sys.executable
        script_path = _DATA_DIR.joinpath("trivial_script.py")
        env = os.environ.copy()
        env["PYTHONPATH"] = _SCRIPTS_DIR.resolve().as_posix()
        subprocess.run(
            [python, script_path.resolve().as_posix(), "--ui", "tk", "--auto-close"],
            timeout=5,
            check=True,
            env=env,
        )
