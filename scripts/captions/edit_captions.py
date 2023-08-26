import csv
import inspect
import os
import tkinter as tk
import tkinter.filedialog as filedialog
from ctypes import windll
from datetime import datetime

from messaging import Colour, Messenger
from webvtt import Segment, WebVTT


def _remind_to_review_low_confidence() -> None:
    print(inspect.cleandoc("""Don't forget to review low-confidence cues on BoxCast before running this script.
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
        Messenger.fatal("Select the VTT file with the captions.")


def _read_time(message: str, vtt: WebVTT, start: bool) -> datetime:
    while True:
        print(message)
        # Show expected format
        time_str = input(Messenger.colour('(HH:MM:SS) ', Colour.GREY))
        # Allow blank values only if this is the beginning of the segment to cut
        if not time_str and start:
            return None
        elif not time_str and not start:
            Messenger.error("Blank values are not allowed. ", end="")
            continue
        # Check for special values
        if time_str == "start":
            return vtt.earliest_caption().start_time
        elif time_str == "end":
            return vtt.latest_caption().start_time
        # Parse time
        try:
            time = datetime.strptime(time_str, "%H:%M:%S")
        except ValueError:
            Messenger.error("Invalid value. ", end="")
            continue
        # Check that at least one caption has a matching start time
        captions = vtt.captions_starting_at(time)
        if not captions:
            Messenger.error(f"No caption found which starts at '{time_str}'. ", end="")
            continue
        elif len(captions) >= 2:
            Messenger.warn(f"Found {len(captions)} captions starting at '{time_str}'.")
        # If this is the beginning of the segment to cut, take the latest caption. Otherwise, take the earliest one.
        captions.sort(key = lambda x: x.start_time)
        return captions[-1].start_time if start else captions[0].start_time


def _read_segment(vtt: WebVTT) -> Segment:
    start_time = _read_time("Enter the start time of the first caption to cut.", vtt, True)
    if not start_time:
        return None
    end_time = _read_time("Enter the start time of the last caption to cut.", vtt, False)
    return Segment(start_time, end_time)


def _read_segments(vtt: WebVTT) -> list[Segment]:
    print(inspect.cleandoc("""Choose the captions to be cut.
        To stop selecting captions, leave the input blank and press ENTER.
        You can enter 'start' to select the earliest caption and 'end' to select the latest caption."""))
    print()
    segments = []
    i = 1
    while True:
        print(f"SEGMENT {i}")
        segment = _read_segment(vtt)
        print()
        if segment is None:
            break
        segments.append(segment)
        i += 1
    return segments


def _read_substitutions() -> list[tuple[str, str]]:
    directory = os.path.dirname(os.path.realpath(__file__))
    filename = os.path.join(directory, "substitutions.csv")
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
    segments = _read_segments(vtt)
    if not segments:
        Messenger.warn("No captions removed.")
    for s in segments:
        vtt.remove(s)
    # Do substitutions
    print()
    substitutions = _read_substitutions()
    old_width = max([len(x[0]) for x in substitutions])
    new_width = max([len(x[1]) for x in substitutions])
    for (old_text, new_text) in substitutions:
        occurrences = vtt.replace(old_text, new_text)
        if occurrences > 0:
            print(f"{old_text.rjust(old_width)} --> {new_text.rjust(new_width)}: {occurrences} occurrences")
    # Save file
    directory = os.path.dirname(filename)
    now = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_filename = os.path.join(directory, f"edited_captions_{now}.vtt")
    vtt.save(out_filename)


if __name__ == "__main__":
    main()
