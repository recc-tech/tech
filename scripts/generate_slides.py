import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable, List, Optional, Set

import autochecklist
from args import ReccArgs
from autochecklist import Messenger, TaskModel, TaskStatus
from lib import ReccDependencyProvider
from lib.slides import (
    Config,
    Slide,
    SlideBlueprint,
    SlideBlueprintReader,
    SlideGenerator,
)

_FULLSCREEN_STYLE = "fullscreen"
_LOWER_THIRD_STYLE = "lower-third"


class GenerateSlidesArgs(ReccArgs):
    NAME = "generate_slides"
    DESCRIPTION = "This script will generate simple slides to be used in case the usual system is not working properly."

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        super().__init__(args, error)
        self.styles: Set[str] = (
            {_FULLSCREEN_STYLE, _LOWER_THIRD_STYLE}
            if args.demo
            else set(args.style or {_LOWER_THIRD_STYLE})
        )
        self.show_browser: bool = args.show_browser
        self.demo: bool = args.demo

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-s",
            "--style",
            action="append",
            choices=[_FULLSCREEN_STYLE, _LOWER_THIRD_STYLE],
            help="Style of the slides.",
        )
        parser.add_argument(
            "--show-browser",
            action="store_true",
            help='If this flag is provided, then browser windows opened by the script will be shown. Otherwise, the Selenium web driver will run in "headless" mode, where no browser window is visible.',
        )
        parser.add_argument(
            "--demo",
            action="store_true",
            help="Generate a small number slides with pre-determined text for demonstration purposes. This overrides the --style argument.",
        )
        return super().set_up_parser(parser)


class GenerateSlidesConfig(Config):
    def __init__(
        self,
        args: GenerateSlidesArgs,
        profile: Optional[str] = None,
        strict: bool = False,
        allow_multiple_only_for_testing: bool = False,
    ) -> None:
        super().__init__(
            args,
            profile=profile,
            strict=strict,
            allow_multiple_only_for_testing=allow_multiple_only_for_testing,
        )
        self._args = args

    @property
    def out_dir(self) -> Path:
        return self.assets_by_service_dir

    @property
    def message_notes_file(self) -> Path:
        return self.out_dir.joinpath(self.message_notes_filename)

    @property
    def lyrics_file(self) -> Path:
        return self.out_dir.joinpath(self.lyrics_filename)

    @property
    def blueprints_file(self) -> Path:
        return self.out_dir.joinpath(self.blueprints_filename)


blueprints: List[SlideBlueprint] = []


def read_input(
    args: GenerateSlidesArgs,
    config: GenerateSlidesConfig,
    reader: SlideBlueprintReader,
    messenger: Messenger,
) -> None:
    global blueprints
    if args.demo:
        blueprints = _get_demo_slides()
    else:
        while True:
            if config.blueprints_file.is_file():
                messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Reading previous data from {config.blueprints_file.as_posix()}...",
                )
                blueprints += reader.load_json(config.blueprints_file)
                if len(blueprints) > 0:
                    # If JSON input is provided, don't use anything else
                    break
            if config.message_notes_file.is_file():
                messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Reading message notes from {config.message_notes_file.as_posix()}...",
                )
                blueprints += reader.load_message_notes(config.message_notes_file)
            if config.lyrics_file.is_file():
                messenger.log_status(
                    TaskStatus.RUNNING,
                    f"Reading lyrics from {config.lyrics_file.as_posix()}...",
                )
                blueprints += reader.load_lyrics(config.lyrics_file)
            if len(blueprints) > 0:
                break
            else:
                messenger.wait(
                    f"Get the message slides from Planning Center Online and save them in {config.message_notes_file.as_posix()}."
                    f" If you'd like to generate slides for the lyrics, save the lyrics for all the songs in {config.lyrics_file.as_posix()}."
                )

    messenger.log_status(TaskStatus.DONE, f"{len(blueprints)} slides found.")


def save_blueprints(
    config: GenerateSlidesConfig, reader: SlideBlueprintReader, messenger: Messenger
) -> None:
    messenger.log_status(
        TaskStatus.RUNNING,
        f"Saving slide contents to {config.blueprints_file.as_posix()}...",
    )
    reader.save_json(config.blueprints_file, blueprints)
    messenger.log_status(
        TaskStatus.DONE,
        f"Slide blueprints saved to {config.blueprints_file.as_posix()}.",
    )


def generate_slides(
    args: GenerateSlidesArgs,
    config: GenerateSlidesConfig,
    generator: SlideGenerator,
    messenger: Messenger,
) -> None:
    slides: List[Slide] = []
    if _FULLSCREEN_STYLE in args.styles:
        messenger.log_status(TaskStatus.RUNNING, "Generating fullscreen images...")
        blueprints_with_prefix = [
            b.with_name(f"FULL{i} - {b.name}" if b.name else f"FULL{i}")
            for i, b in enumerate(blueprints, start=1)
        ]
        slides += generator.generate_fullscreen_slides(blueprints_with_prefix)
    if _LOWER_THIRD_STYLE in args.styles:
        messenger.log_status(
            TaskStatus.RUNNING, "Generating lower third images with a background..."
        )
        blueprints_with_prefix = [
            b.with_name(f"LTD{i} - {b.name}" if b.name else f"LTD{i}")
            for i, b in enumerate(blueprints, start=1)
        ]
        slides += generator.generate_lower_third_slides(blueprints_with_prefix)

    messenger.log_status(TaskStatus.RUNNING, "Saving images...")
    for s in slides:
        s.save(config.out_dir)
    messenger.log_status(
        TaskStatus.DONE, f"{len(slides)} images saved to {config.out_dir.as_posix()}."
    )


def _get_demo_slides() -> List[SlideBlueprint]:
    return [
        SlideBlueprint(body_text="Hello", footer_text="", name="short-no-footer"),
        SlideBlueprint(
            body_text="Hello there!", footer_text="Footer", name="short-with-footer"
        ),
        SlideBlueprint(
            body_text=(
                "“Then Fingolfin beheld… the utter ruin of the Noldor, and the defeat beyond redress of all their houses;"
                + " and filled with wrath and despair he mounted upon Rochallor his great horse and rode forth alone, and none might restrain him."
                + " He passed over Dor-nu-Fauglith like a wind amid the dust, and all that beheld his onset fled in amaze, thinking that Oromë himself was come:"
                + " for a great madness of rage was upon him, so that his eyes shone like the eyes of the Valar."
                + " Thus he came alone to Angband’s gates, and he sounded his horn, and smote once more upon the brazen doors, and challenged Morgoth to come forth to single combat."
                + " And Morgoth came.” (J.R.R. Tolkien, The Silmarillion)"
            ),
            footer_text="",
            name="long-no-footer",
        ),
        SlideBlueprint(
            body_text=(
                "Then were the king's scribes called at that time in the third"
                + " month, that is, the month Sivan, on the three and"
                + " twentieth day thereof; and it was written according to all"
                + " that Mordecai commanded unto the Jews, and to the"
                + " lieutenants, and the deputies and rulers of the provinces"
                + " which are from India unto Ethiopia, an hundred twenty and"
                + " seven provinces, unto every province according to the"
                + " writing thereof, and unto every people after their"
                + " language, and to the Jews according to their writing, and"
                + " according to their language."
            ),
            footer_text="Esther 8:9 (KJV)",
            name="long-with-footer",
        ),
    ]


if __name__ == "__main__":
    args = GenerateSlidesArgs.parse(sys.argv)
    config = GenerateSlidesConfig(args, profile=None, strict=False)
    tasks = TaskModel(
        name="main",
        subtasks=[
            TaskModel(
                name="read_input",
                description="Failed to read input.",
                only_auto=True,
            ),
            TaskModel(
                name="save_blueprints",
                description="Failed to save blueprints.",
                prerequisites={"read_input"},
                only_auto=True,
            ),
            TaskModel(
                name="generate_slides",
                description="Failed to make slides.",
                prerequisites={"read_input"},
                only_auto=True,
            ),
        ],
    )
    dependency_provider = ReccDependencyProvider(
        args=args,
        config=config,
        log_file=config.generate_slides_log,
        script_name="Generate Slides",
        description=GenerateSlidesArgs.DESCRIPTION,
        show_statuses_by_default=True,
        headless=not args.show_browser,
        webdriver_log=config.generate_slides_webdriver_log,
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dependency_provider,
        tasks=tasks,
        module=sys.modules[__name__],
    )
