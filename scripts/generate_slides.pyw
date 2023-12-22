import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional, Set, Tuple

from autochecklist import (
    ConsoleMessenger,
    FileMessenger,
    FunctionFinder,
    Messenger,
    Script,
    TaskModel,
    TaskStatus,
    TkMessenger,
)
from common import ReccConfig, ReccWebDriver, parse_directory
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


class GenerateSlidesConfig(ReccConfig):
    def __init__(
        self,
        home_dir: Path,
        out_dir: Path,
        styles: Set[str],
        now: datetime,
        show_browser: bool,
        ui: Literal["console", "tk"],
        verbose: bool,
        no_run: bool,
    ) -> None:
        super().__init__(
            home_dir=home_dir, now=now, ui=ui, verbose=verbose, no_run=no_run
        )
        self.out_dir = out_dir
        self.styles = styles
        self.show_browser = show_browser
        self.blueprints: List[SlideBlueprint] = []

    @property
    def log_file(self) -> Path:
        timestamp = f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')}"
        return self.log_dir.joinpath(f"{timestamp} generate_slides.log")

    @property
    def webdriver_log_file(self) -> Path:
        timestamp = f"{self.now.strftime('%Y-%m-%d')} {self.now.strftime('%H-%M-%S')}"
        return self.log_dir.joinpath(f"{timestamp} generate_slides_webdriver.log")

    @property
    def json_file(self) -> Path:
        return self.out_dir.joinpath("slides.json")

    @property
    def message_notes_file(self) -> Path:
        return self.out_dir.joinpath("message-notes.txt")

    @property
    def lyrics_file(self) -> Path:
        return self.out_dir.joinpath("lyrics.txt")


class GenerateSlidesScript(Script[GenerateSlidesConfig]):
    def __init__(self) -> None:
        self._web_driver: Optional[ReccWebDriver] = None

    def create_config(self) -> GenerateSlidesConfig:
        parser = ArgumentParser(description=_DESCRIPTION)

        parser.add_argument(
            "-o",
            "--out-dir",
            default=f"D:\\Users\\Tech\\Documents\\vMix Assets\\By Service\\{datetime.now().strftime('%Y-%m-%d')}\\",
            type=lambda x: parse_directory(x, create=True),
            help="Directory in which to place the generated images.",
        )
        parser.add_argument(
            "-s",
            "--style",
            action="append",
            choices=[
                _FULLSCREEN_STYLE,
                _LOWER_THIRD_CLEAR_STYLE,
                _LOWER_THIRD_DARK_STYLE,
            ],
            help="Style of the slides.",
        )

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
            "--ui",
            choices=["console", "tk"],
            default="tk",
            help="User interface to use.",
        )
        advanced_args.add_argument(
            "--verbose",
            action="store_true",
            help="This flag is only applicable when the flag --text-ui is also provided. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
        )

        args = parser.parse_args()
        return GenerateSlidesConfig(
            home_dir=args.home_dir,
            out_dir=args.out_dir,
            styles=set(args.style or {_LOWER_THIRD_DARK_STYLE}),
            now=datetime.now(),
            show_browser=args.show_browser,
            ui=args.ui,
            verbose=args.verbose,
            no_run=False,
        )

    def create_messenger(self, config: GenerateSlidesConfig) -> Messenger:
        file_messenger = FileMessenger(config.log_file)
        input_messenger = (
            ConsoleMessenger(description=_DESCRIPTION, show_task_status=config.verbose)
            if config.ui == "console"
            else TkMessenger(title="Generate Slides", description=_DESCRIPTION)
        )
        return Messenger(file_messenger, input_messenger)

    def create_services(
        self, config: GenerateSlidesConfig, messenger: Messenger
    ) -> Tuple[TaskModel | Path, FunctionFinder]:
        task_model = TaskModel(
            name="main",
            subtasks=[
                TaskModel(name="read_input", description="Failed to read input."),
                TaskModel(
                    name="save_json",
                    description="Failed to save blueprints.",
                    prerequisites={"read_input"},
                ),
                TaskModel(
                    name="generate_slides",
                    description="Failed to make slides.",
                    prerequisites={"read_input"},
                ),
            ],
        )
        self._web_driver = ReccWebDriver(
            messenger=messenger,
            headless=not config.show_browser,
            log_file=config.webdriver_log_file,
        )
        bible_verse_finder = BibleVerseFinder(
            # No need for a cancellation token since this script is linear and
            # the user can just cancel the whole thing
            self._web_driver,
            messenger,
            cancellation_token=None,
        )
        reader = SlideBlueprintReader(messenger, bible_verse_finder)
        generator = SlideGenerator(messenger)
        function_finder = FunctionFinder(
            # Use the current module
            module=sys.modules[__name__],
            arguments=[
                messenger,
                self._web_driver,
                bible_verse_finder,
                reader,
                generator,
                config,
            ],
            messenger=messenger,
        )
        return task_model, function_finder

    def shut_down(self, config: GenerateSlidesConfig) -> None:
        if self._web_driver:
            self._web_driver.quit()


def read_input(
    config: GenerateSlidesConfig, reader: SlideBlueprintReader, messenger: Messenger
) -> None:
    blueprints: List[SlideBlueprint] = []
    while True:
        if config.json_file.is_file():
            messenger.log_status(
                TaskStatus.RUNNING,
                f"Reading previous data from {config.json_file.as_posix()}...",
            )
            blueprints += reader.load_json(config.json_file)
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
                f"Get the message slides from Planning Center Online and save them in {config.message_notes_file.as_posix()}. If you'd like to generate slides for the lyrics, save the lyrics for all the songs in {config.lyrics_file.as_posix()}."
            )

    config.blueprints = blueprints
    messenger.log_status(TaskStatus.DONE, f"{len(blueprints)} slides found.")


def save_json(
    config: GenerateSlidesConfig,
    reader: SlideBlueprintReader,
    messenger: Messenger,
):
    messenger.log_status(
        TaskStatus.RUNNING,
        f"Saving slide contents to {config.json_file.as_posix()}...",
    )
    reader.save_json(config.json_file, config.blueprints)
    messenger.log_status(
        TaskStatus.DONE, f"Slide blueprints saved to {config.json_file.as_posix()}."
    )


def generate_slides(
    config: GenerateSlidesConfig,
    generator: SlideGenerator,
    messenger: Messenger,
) -> None:
    slides: List[Slide] = []
    if _FULLSCREEN_STYLE in config.styles:
        messenger.log_status(TaskStatus.RUNNING, "Generating fullscreen images...")
        blueprints_with_prefix = [
            b.with_name(f"FULL{i} - {b.name}" if b.name else f"FULL{i}")
            for i, b in enumerate(config.blueprints, start=1)
        ]
        slides += generator.generate_fullscreen_slides(blueprints_with_prefix)
    if _LOWER_THIRD_CLEAR_STYLE in config.styles:
        messenger.log_status(
            TaskStatus.RUNNING,
            "Generating lower third images without a background...",
        )
        blueprints_with_prefix = [
            b.with_name(f"LTC{i} - {b.name}" if b.name else f"LTC{i}")
            for i, b in enumerate(config.blueprints, start=1)
        ]
        slides += generator.generate_lower_third_slide(
            blueprints_with_prefix, show_backdrop=False
        )
    if _LOWER_THIRD_DARK_STYLE in config.styles:
        messenger.log_status(
            TaskStatus.RUNNING, "Generating lower third images with a background..."
        )
        blueprints_with_prefix = [
            b.with_name(f"LTD{i} - {b.name}" if b.name else f"LTD{i}")
            for i, b in enumerate(config.blueprints, start=1)
        ]
        slides += generator.generate_lower_third_slide(
            blueprints_with_prefix, show_backdrop=True
        )

    messenger.log_status(TaskStatus.RUNNING, "Saving images...")
    for s in slides:
        s.save(config.out_dir)
    messenger.log_status(
        TaskStatus.DONE, f"{len(slides)} images saved to {config.out_dir.as_posix()}."
    )


if __name__ == "__main__":
    GenerateSlidesScript().run()
