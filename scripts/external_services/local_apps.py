"""
Functions for launching applications installed on this computer.
"""

import subprocess
from pathlib import Path


def launch_firefox(url: str) -> None:
    # Use Popen so this doesn't block
    subprocess.Popen(["firefox", url])


def launch_vmix(preset: Path) -> None:
    # Use Popen so this doesn't block
    subprocess.Popen(["vMix64", str(preset.resolve())])
