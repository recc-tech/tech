import logging
import shutil
import stat
from pathlib import Path

from config import Config
from messenger import Messenger


def copy_captions_original_to_without_worship(messenger: Messenger, config: Config):
    _mark_read_only_and_copy(
        config.captions_dir.joinpath("original.vtt"),
        config.captions_dir.joinpath("without_worship.vtt"),
        messenger,
    )


def copy_captions_without_worship_to_final(messenger: Messenger, config: Config):
    _mark_read_only_and_copy(
        config.captions_dir.joinpath("original.vtt"),
        config.captions_dir.joinpath("without_worship.vtt"),
        messenger,
    )


def _mark_read_only_and_copy(source: Path, destination: Path, messenger: Messenger):
    if not source.exists():
        raise ValueError(f"File '{source}' does not exist.")

    # Mark the original file as read-only
    source.chmod(stat.S_IREAD)
    messenger.log(logging.DEBUG, f"Marked '{source}' as read-only.")

    if destination.exists():
        messenger.log(
            logging.WARN,
            f"File '{destination}' already exists and will be overwritten.",
        )

    # Copy the file
    shutil.copy(src=source, dst=destination)
    messenger.log(logging.DEBUG, f"Copied '{source}' to '{destination}'.")
