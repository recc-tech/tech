from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from pathlib import Path
from typing import List

from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    Messenger,
    TaskStatus,
    set_current_task_name,
)
from slides import SlideBlueprint, SlideBlueprintReader, SlideGenerator

DESCRIPTION = "This script will generate simple slides to be used in case the usual system is not working properly."

FULLSCREEN_STYLE = "fullscreen"
LOWER_THIRD_CLEAR_STYLE = "lower-third-clear"
LOWER_THIRD_DARK_STYLE = "lower-third-dark"


def main():
    args = _parse_args()
    output_directory: Path = args.out_dir
    home_directory: Path = args.home_dir

    log_dir = home_directory.joinpath("Logs")
    date_ymd = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_dir.joinpath(f"{date_ymd} {current_time} generate_slides.log")
    file_messenger = FileMessenger(log_file)
    input_messenger = ConsoleMessenger(description=DESCRIPTION)
    messenger = Messenger(file_messenger, input_messenger)

    try:
        reader = SlideBlueprintReader(messenger)

        blueprints: List[SlideBlueprint] = []
        if args.json_input:
            set_current_task_name("load_json")
            blueprints += reader.load_json(args.json_input)
        if args.message_notes:
            set_current_task_name("load_message_notes")
            blueprints += reader.load_message_notes(args.message_notes)
        if args.lyrics:
            set_current_task_name("load_lyrics")
            for lyrics_file in args.lyrics:
                blueprints += reader.load_lyrics(lyrics_file)

        if not args.json_input:
            set_current_task_name("save_json")
            reader.save_json(output_directory.joinpath("slides.json"), blueprints)

        set_current_task_name("generate_slides")
        generator = SlideGenerator(messenger)
        if args.style == FULLSCREEN_STYLE:
            slides = generator.generate_fullscreen_slides(blueprints)
        elif args.style == LOWER_THIRD_CLEAR_STYLE:
            slides = generator.generate_lower_third_slide(
                blueprints, show_backdrop=False
            )
        elif args.style == LOWER_THIRD_DARK_STYLE:
            slides = generator.generate_lower_third_slide(
                blueprints, show_backdrop=True
            )
        else:
            raise ValueError("")

        set_current_task_name("save_slides")
        for s in slides:
            path = output_directory.joinpath(s.name)
            if path.suffix.lower() != ".png":
                path = path.with_suffix(".png")
            s.image.save(path, format="PNG")

        slide_or_slides = "slide" if len(slides) == 1 else "slides"
        messenger.log_status(
            TaskStatus.DONE,
            f"All done! {len(slides)} {slide_or_slides} generated.",
            task_name="SCRIPT MAIN",
        )
    finally:
        messenger.close()


def _parse_args() -> Namespace:
    parser = ArgumentParser(description=DESCRIPTION)

    parser.add_argument(
        "--message-notes",
        "-n",
        type=lambda x: _parse_file(x, extension=".txt"),
        help="Text file from which to read the message notes.",
    )
    parser.add_argument(
        "--lyrics",
        "-l",
        type=lambda x: _parse_file(x, extension=".txt"),
        action="append",
        help="Text file from which to read song lyrics.",
    )
    parser.add_argument(
        "--json-input",
        "-j",
        type=lambda x: _parse_file(x, extension=".json"),
        help="JSON file from which to take input.",
    )
    parser.add_argument(
        "--out-dir",
        "-o",
        required=True,
        type=_parse_directory,
        help="Directory in which to place the generated images.",
    )
    parser.add_argument(
        "--style",
        "-s",
        default=FULLSCREEN_STYLE,
        choices=[FULLSCREEN_STYLE, LOWER_THIRD_CLEAR_STYLE, LOWER_THIRD_DARK_STYLE],
        help="Style of the slides.",
    )

    advanced_args = parser.add_argument_group("Advanced arguments")
    advanced_args.add_argument(
        "--home-dir",
        type=_parse_directory,
        default="D:\\Users\\Tech\\Documents",
        help="The home directory.",
    )

    args = parser.parse_args()

    if not args.message_notes and not args.lyrics and not args.json_input:
        parser.error("You must specify at least one form of input file.")
    if (args.message_notes or args.lyrics) and args.json_input:
        parser.error("You cannot provide both plaintext input and JSON input.")

    return args


# TODO: Move these kinds of argument parsing helpers to a separate file?
def _parse_file(filename: str, extension: str = "") -> Path:
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


def _parse_directory(path_str: str) -> Path:
    path = Path(path_str)

    if not path.exists():
        raise ArgumentTypeError(f"Path '{path_str}' does not exist.")
    if not path.is_dir():
        raise ArgumentTypeError(f"Path '{path_str}' is not a directory.")
    # TODO: Check whether the path is accessible?

    path = path.resolve()
    return path


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program cancelled.")
