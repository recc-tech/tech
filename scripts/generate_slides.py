from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path

from slides import (
    SlideOutput,
    generate_fullscreen_slides,
    load_json,
    load_txt,
    parse_slides,
    save_json,
)


def main():
    args = _parse_args()

    output_directory: Path = args.out_dir

    if args.text_input:
        lines = load_txt(args.text_input)
        slides = parse_slides(lines)
        save_json(output_directory.joinpath("slides.json"), slides)
    else:
        slides = load_json(args.json_input)

    images = generate_fullscreen_slides(slides)

    for i, img in enumerate(images):
        out_file = output_directory.joinpath(_slide_name(img, i))
        img.image.save(out_file, format="PNG")


def _parse_args() -> Namespace:
    parser = ArgumentParser(description="Generate simple slides from text.")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--text-input",
        "-t",
        type=lambda x: _parse_file(x, extension=".txt"),
        help="Text file from which to take input.",
    )
    input_group.add_argument(
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

    return parser.parse_args()


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


def _slide_name(slide: SlideOutput, index: int) -> str:
    name = slide.name if slide.name else f"Slide {index}.png"
    if not name.lower().endswith(".png"):
        name = f"{name}.png"
    return name


if __name__ == "__main__":
    main()
