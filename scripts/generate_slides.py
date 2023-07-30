import traceback
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    Messenger,
    ProblemLevel,
    TaskStatus,
    TkMessenger,
    set_current_task_name,
)
from common import ReccWebDriver, parse_directory, parse_file
from slides import (
    BibleVerseFinder,
    Slide,
    SlideBlueprint,
    SlideBlueprintReader,
    SlideGenerator,
)

_DESCRIPTION = "This script will generate simple slides to be used in case the usual system is not working properly."

_FULLSCREEN_STYLE = "fullscreen"
_LOWER_THIRD_CLEAR_STYLE = "lower-third-clear"
_LOWER_THIRD_DARK_STYLE = "lower-third-dark"

_SCRIPT_MAIN = "SCRIPT MAIN"


def main():
    set_current_task_name(_SCRIPT_MAIN)

    cmd_args = _parse_args()
    output_directory: Path = cmd_args.out_dir
    home_directory: Path = cmd_args.home_dir

    log_dir = home_directory.joinpath("Logs")
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_dir.joinpath(f"{date_ymd} {current_time} generate_slides.log")
    file_messenger = FileMessenger(log_file)
    input_messenger = (
        ConsoleMessenger(description=_DESCRIPTION)
        if cmd_args.text_ui
        else TkMessenger(description=_DESCRIPTION)
    )
    messenger = Messenger(file_messenger, input_messenger)

    try:
        message_notes: Optional[Path] = cmd_args.message_notes
        lyrics: List[Path] = cmd_args.message_notes
        json_input: Optional[Path] = cmd_args.json_input
        if not message_notes and not lyrics and not json_input:
            (message_notes, lyrics, json_input) = _locate_input(
                output_directory, messenger
            )

        messenger.log_status(TaskStatus.RUNNING, "Starting the script...")

        web_driver = ReccWebDriver(headless=not cmd_args.show_browser)
        bible_verse_finder = BibleVerseFinder(web_driver, messenger)
        reader = SlideBlueprintReader(messenger, bible_verse_finder)
        generator = SlideGenerator(messenger)

        messenger.log_status(TaskStatus.RUNNING, "Running tasks...")

        set_current_task_name("read_input")
        blueprints = _read_input(json_input, message_notes, lyrics, reader, messenger)

        if not json_input:
            set_current_task_name("save_input")
            _save_json(blueprints, output_directory, reader, messenger)

        set_current_task_name("generate_slides")
        slides = _generate_slides(blueprints, cmd_args.style, generator, messenger)

        set_current_task_name("save_slides")
        _save_slides(slides, output_directory, messenger)

        set_current_task_name(_SCRIPT_MAIN)
        messenger.log_status(
            TaskStatus.DONE, f"All done! {len(slides)} slides generated."
        )
    except Exception as e:
        messenger.log_problem(
            ProblemLevel.FATAL, f"Error: {e}.", stacktrace=traceback.format_exc()
        )
        messenger.log_status(TaskStatus.DONE, "Script failed.")
    except KeyboardInterrupt as e:
        messenger.log_status(
            TaskStatus.DONE, "Script cancelled by the user.", file_only=True
        )
        print("Program cancelled.")
    finally:
        messenger.close()


def _parse_args() -> Namespace:
    parser = ArgumentParser(description=_DESCRIPTION)

    parser.add_argument(
        "-n",
        "--message-notes",
        type=lambda x: parse_file(x, extension=".txt"),
        help="Text file from which to read the message notes.",
    )
    parser.add_argument(
        "-l",
        "--lyrics",
        type=lambda x: parse_file(x, extension=".txt"),
        action="append",
        help="Text file from which to read song lyrics.",
    )
    parser.add_argument(
        "-j",
        "--json-input",
        type=lambda x: parse_file(x, extension=".json"),
        help="JSON file from which to take input.",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        default=f"D:\\Users\\Tech\\Documents\\vMix Assets\\By Service\\{datetime.now().strftime('%Y-%m-%d')}\\",
        type=parse_directory,
        help="Directory in which to place the generated images.",
    )
    parser.add_argument(
        "-s",
        "--style",
        action="append",
        choices=[_FULLSCREEN_STYLE, _LOWER_THIRD_CLEAR_STYLE, _LOWER_THIRD_DARK_STYLE],
        help="Style of the slides.",
    )

    # TODO: Add an option to clear out all the existing slides

    advanced_args = parser.add_argument_group("Advanced arguments")
    advanced_args.add_argument(
        "--home-dir",
        type=parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
    )
    advanced_args.add_argument(
        "--show-browser",
        action="store_true",
        help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
    )
    advanced_args.add_argument(
        "--text-ui",
        action="store_true",
        help="If this flag is provided, then user interactions will be performed via a simpler terminal-based UI.",
    )

    args = parser.parse_args()

    if (args.message_notes or args.lyrics) and args.json_input:
        parser.error("You cannot provide both plaintext input and JSON input.")

    if not args.style:
        args.style = [_LOWER_THIRD_DARK_STYLE]

    return args


def _locate_input(
    directory: Path, messenger: Messenger
) -> Tuple[Optional[Path], List[Path], Optional[Path]]:
    messenger.log_status(TaskStatus.RUNNING, "Looking for input...")

    json_file = directory.joinpath("slides.json")
    if json_file.is_file():
        return (None, [], json_file)

    message_notes_file = directory.joinpath("message-notes.txt")
    lyrics_file = directory.joinpath("lyrics.txt")
    while True:
        out_notes = message_notes_file if message_notes_file.is_file() else None
        out_lyrics = [lyrics_file] if lyrics_file.is_file() else []
        if out_notes or out_lyrics:
            return (out_notes, out_lyrics, None)
        else:
            messenger.wait(
                f"Get the message slides from Planning Center Online and save them in {message_notes_file}. If you'd like to generate slides for the lyrics, save the lyrics for all the songs in {lyrics_file}."
            )


def _read_input(
    json_input: Optional[Path],
    message_notes: Optional[Path],
    lyrics: List[Path],
    reader: SlideBlueprintReader,
    messenger: Messenger,
) -> List[SlideBlueprint]:
    blueprints: List[SlideBlueprint] = []
    if json_input:
        messenger.log_status(
            TaskStatus.RUNNING,
            f"Reading previous data from {json_input.as_posix()}...",
        )
        blueprints += reader.load_json(json_input)
    if message_notes:
        messenger.log_status(
            TaskStatus.RUNNING,
            f"Reading message notes from {message_notes.as_posix()}...",
        )
        blueprints += reader.load_message_notes(message_notes)
    if lyrics:
        lyrics_file_list = ", ".join([f.as_posix() for f in lyrics])
        messenger.log_status(
            TaskStatus.RUNNING, f"Reading lyrics from {lyrics_file_list}..."
        )
        for lyrics_file in lyrics:
            blueprints += reader.load_lyrics(lyrics_file)
    messenger.log_status(TaskStatus.DONE, f"{len(blueprints)} slides found.")
    return blueprints


def _save_json(
    blueprints: List[SlideBlueprint],
    output_directory: Path,
    reader: SlideBlueprintReader,
    messenger: Messenger,
):
    json_file = output_directory.joinpath("slides.json")
    messenger.log_status(
        TaskStatus.RUNNING,
        f"Saving slide contents to {json_file.as_posix()}...",
    )
    reader.save_json(json_file, blueprints)
    messenger.log_status(
        TaskStatus.DONE, f"Slide contents saved to {json_file.as_posix()}."
    )


def _generate_slides(
    blueprints: List[SlideBlueprint],
    styles: List[str],
    generator: SlideGenerator,
    messenger: Messenger,
) -> List[Slide]:
    slides: List[Slide] = []
    if _FULLSCREEN_STYLE in styles:
        messenger.log_status(TaskStatus.RUNNING, "Generating fullscreen images...")
        blueprints_with_prefix = [
            b.with_name(f"FULL{i} - {b.name}" if b.name else f"FULL{i}")
            for i, b in enumerate(blueprints, start=1)
        ]
        slides += generator.generate_fullscreen_slides(blueprints_with_prefix)
    if _LOWER_THIRD_CLEAR_STYLE in styles:
        messenger.log_status(
            TaskStatus.RUNNING,
            "Generating lower third images without a background...",
        )
        blueprints_with_prefix = [
            b.with_name(f"LTC{i} - {b.name}" if b.name else f"LTC{i}")
            for i, b in enumerate(blueprints, start=1)
        ]
        slides += generator.generate_lower_third_slide(
            blueprints_with_prefix, show_backdrop=False
        )
    if _LOWER_THIRD_DARK_STYLE in styles:
        messenger.log_status(
            TaskStatus.RUNNING, "Generating lower third images with a background..."
        )
        blueprints_with_prefix = [
            b.with_name(f"LTD{i} - {b.name}" if b.name else f"LTD{i}")
            for i, b in enumerate(blueprints, start=1)
        ]
        slides += generator.generate_lower_third_slide(
            blueprints_with_prefix, show_backdrop=True
        )
    messenger.log_status(TaskStatus.DONE, f"{len(slides)} slides generated.")
    return slides


def _save_slides(slides: List[Slide], output_directory: Path, messenger: Messenger):
    messenger.log_status(TaskStatus.RUNNING, "Saving images...")
    for s in slides:
        s.save(output_directory)
    messenger.log_status(TaskStatus.DONE, "Images saved.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram cancelled.")
