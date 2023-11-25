import sys
from pathlib import Path
from typing import Callable


def run_with_or_without_terminal(main: Callable[[], None], error_file: Path):
    """
    If the program is being run from the command line, then run main directly.
    If the program is being run *without* a terminal window, then redirect
    stderr to the given file.
    This ensures errors that would normally be printed to the terminal do not
    silently kill the program.
    """
    # pythonw sets sys.stderr to None
    has_terminal = sys.stderr is not None  # type: ignore
    if has_terminal:
        main()
    else:
        with open(error_file, "w", encoding="utf-8") as se:
            sys.stderr = se
            main()
        # No need to keep the file around if the program exited successfully
        error_file.unlink(missing_ok=True)
