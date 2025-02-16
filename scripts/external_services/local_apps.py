"""
Functions for launching applications installed on this computer.
"""

import subprocess
from pathlib import Path


def launch_firefox(url: str, fullscreen: bool = False) -> None:
    if fullscreen:
        args = ["firefox", "--new-window", url, "--kiosk"]
    else:
        args = ["firefox", url]
    # Use Popen so this doesn't block
    subprocess.Popen(args)


def launch_vmix(preset: Path) -> None:
    # Use Popen so this doesn't block
    subprocess.Popen(["vMix64", str(preset.resolve())])
