from argparse import ArgumentTypeError
from pathlib import Path


def parse_non_empty_string(raw_input: str) -> str:
    if not raw_input or not raw_input.strip():
        raise ArgumentTypeError("The value cannot be empty.")
    return raw_input.strip()


def parse_directory(
    path_str: str, missing_ok: bool = False, create: bool = False
) -> Path:
    path = Path(path_str)

    if create:
        try:
            path.mkdir(exist_ok=True, parents=False)
        except FileNotFoundError:
            raise ArgumentTypeError(
                f"Path '{path_str}' does not exist and could not be created."
            ) from FileNotFoundError

    if not missing_ok and not path.exists():
        message = f"Path '{path_str}' does not exist."
        if path_str.endswith('"') or path_str.endswith("'"):
            message = f"{message} Note that if you provided the path in quotes and with a trailing backslash, you must escape that final backslash."
        raise ArgumentTypeError(message)
    if not missing_ok and not path.is_dir():
        raise ArgumentTypeError(f"Path '{path_str}' is not a directory.")

    path = path.resolve()
    return path


def parse_file(filename: str, extension: str = "", missing_ok: bool = False) -> Path:
    path = Path(filename)

    if not missing_ok and not path.exists():
        raise ArgumentTypeError(f"Path '{filename}' does not exist.")
    if not missing_ok and not path.is_file():
        raise ArgumentTypeError(f"Path '{filename}' is not a file.")

    if extension:
        if path.suffix != extension:
            raise ArgumentTypeError(
                f"Expected a file with a {extension} extension, but received a {path.suffix} file."
            )

    return path.resolve()
