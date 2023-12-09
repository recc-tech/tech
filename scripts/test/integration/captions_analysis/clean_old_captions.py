import os
import re
import shutil
from pathlib import Path

OLD_DIR = Path(__file__).resolve().parent.parent.joinpath("raw_old_captions")
NEW_DIR = Path(__file__).resolve().parent.parent.joinpath("captions_data")

ORIGINAL_CAPTIONS_REGEX = re.compile(r"([a-z0-9]{20,20}_captions.vtt|original.vtt)")
FINAL_CAPTIONS_REGEX = re.compile(
    r"(edited_captions_202[23]-\d\d-\d\d_\d{6,6}.vtt|final.vtt)"
)
CAPTIONS_WITHOUT_WORSHIP_REGEX = re.compile(
    r"(?:[Cc]aptions[_ ])?[Ww]ithout[_ ][Ww]orship\s?.vtt"
)


def main():
    NEW_DIR.mkdir(exist_ok=True)
    for dirname, subdirs, filenames in os.walk(OLD_DIR):
        if subdirs:
            print(f"Skipping directory '{dirname}' because it has subdirectories.")
            continue
        src_dir = Path(dirname)
        dst_dir = Path(NEW_DIR).joinpath(src_dir.stem)
        dst_dir.mkdir(exist_ok=True)
        for fname in filenames:
            if ORIGINAL_CAPTIONS_REGEX.fullmatch(fname):
                shutil.copyfile(
                    src=src_dir.joinpath(fname),
                    dst=dst_dir.joinpath("original.vtt"),
                )
            elif FINAL_CAPTIONS_REGEX.fullmatch(fname):
                shutil.copyfile(
                    src=src_dir.joinpath(fname),
                    dst=dst_dir.joinpath("final.vtt"),
                )
            elif CAPTIONS_WITHOUT_WORSHIP_REGEX.fullmatch(fname):
                pass
            else:
                print(f"Unrecognized filename '{fname}' in directory '{dirname}'.")


if __name__ == "__main__":
    main()
