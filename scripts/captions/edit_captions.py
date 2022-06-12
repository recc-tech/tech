from ctypes import windll
from datetime import datetime
from logging import Logger
from webvtt import Segment, WebVTT

import csv
import inspect
import os
import tkinter as tk
import tkinter.filedialog as filedialog


def _remind_to_review_low_confidence() -> None:
    Logger.info(inspect.cleandoc("""Don't forget to review low-confidence cues on BoxCast before running this script.
        Press ENTER to continue..."""))
    input()


def _get_captions_filename() -> str:
    # Ensure image quality is decent
    windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    # Ensure the file dialog opens in front
    root.lift()
    root.withdraw()
    filename = filedialog.askopenfilename(title="Select VTT file")
    if filename:
        return filename
    else:
        Logger.error("Select the VTT file with the captions.")


def _read_time(message: str, allow_empty: bool = False) -> datetime:
    while True:
        time_str = input(message)
        # Blank value
        if not time_str:
            if allow_empty:
                return None
            else:
                print("Blank values are not allowed. ", end="")
                continue
        # Try to parse with milliseconds
        try:
            time = datetime.strptime(time_str, "%H:%M:%S.%f")
            return time
        except ValueError:
            pass
        # Try to parse without milliseconds
        try:
            time = datetime.strptime(time_str, "%H:%M:%S")
            return time
        except ValueError:
            pass
        print("Invalid value. ", end="")


def _read_segment() -> Segment:
    start_time = _read_time("Enter the start time of the first caption to cut.\n>> ", True)
    if not start_time:
        return None
    end_time = _read_time("Enter the start time of the last caption to cut.\n>> ", False)
    return Segment(start_time, end_time)


def _read_substitutions() -> list[tuple[str, str]]:
    filename = "substitutions.csv"
    substitutions = []
    with open(filename, "r", newline="") as f:
        reader = csv.reader(f)
        # Skip header
        next(reader)
        for line in reader:
            if len(line) != 2:
                raise ValueError(
                    f"Invalid row in {filename}: '{','.join(line)}'. Expected two columns but received {len(line)}."
                )
            substitutions.append((line[0], line[1]))
    return substitutions


def main() -> None:
    _remind_to_review_low_confidence()
    # Read captions
    filename = _get_captions_filename()
    vtt = WebVTT.read(filename)
    # Remove captions
    segments = []
    i = 1
    while True:
        print(f"SEGMENT {i}")
        segment = _read_segment()
        print()
        if segment is None:
            break
        segments.append(segment)
        i += 1
    if len(segments) == 0:
        Logger.warn("No captions removed.")
    for s in segments:
        vtt.remove(s)
    # Do substitutions
    substitutions = _read_substitutions()
    def f(x: str) -> str:
        for (old_word, new_word) in substitutions:
            x = x.replace(old_word, new_word)
        return x
    vtt.apply_to_text(f)
    # Save file
    directory = os.path.dirname(filename)
    now = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_filename = os.path.join(directory, f"edited_captions_{now}.vtt")
    vtt.save(out_filename)


if __name__ == "__main__":
    main()
