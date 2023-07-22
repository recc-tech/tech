from argparse import ArgumentTypeError
from pathlib import Path


def parse_non_empty_string(raw_input: str) -> str:
    if not raw_input or not raw_input.strip():
        raise ArgumentTypeError("The value cannot be empty.")
    return raw_input.strip()


def parse_directory(path_str: str) -> Path:
    path = Path(path_str)

    if not path.exists():
        raise ArgumentTypeError(f"Path '{path_str}' does not exist.")
    if not path.is_dir():
        raise ArgumentTypeError(f"Path '{path_str}' is not a directory.")
    # TODO: Check whether the path is accessible?

    path = path.resolve()
    return path


def parse_file(filename: str, extension: str = "") -> Path:
    path = Path(filename)

    if not path.exists():
        raise ArgumentTypeError(f"Path '{filename}' does not exist.")
    if not path.is_file():
        raise ArgumentTypeError(f"Path '{filename}' is not a file.")
    # TODO: Check whether the path is accessible?

    if extension:
        if path.suffix != extension:
            raise ArgumentTypeError(
                f"Expected a file with a {extension} extension, but received a {path.suffix} file."
            )

    return path.resolve()


if __name__ == "__main__":
    print(
        "This module is not runnable. It is only meant to provide helper functions for other scripts."
    )
