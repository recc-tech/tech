"""
Functions for launching applications installed on this computer.
"""

import subprocess


def launch_firefox(url: str) -> None:
    # Use Popen so this doesn't block
    subprocess.Popen(["firefox", url])
