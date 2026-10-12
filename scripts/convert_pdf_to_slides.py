import shutil
import subprocess
import sys
from pathlib import Path
from subprocess import Popen

import autochecklist
from args import ReccArgs
from autochecklist import Messenger, TaskModel, TaskStatus
from config import Config
from lib import ReccDependencyProvider, SimplifiedMessengerSettings


class ConvertPdfToSlidesArgs(ReccArgs):
    NAME = "convert_pdf_to_slides"
    DESCRIPTION = (
        "This script will convert a PDF into separate PNGs to import into ProPresenter"
    )


def convert_pdf_to_slides(
    config: Config,
    messenger: Messenger,
):
    messenger.log_status(TaskStatus.RUNNING, "Waiting for the file to be selected...")
    pdf_path = messenger.input_filename(
        initial_dir=config.assets_by_service_dir,
        file_types=[("PDF documents", "*.pdf")],
    )
    if not pdf_path:
        raise ValueError("no file selected")
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise ValueError(f"'{pdf_path.as_posix()}' does not exist or is not a file")

    messenger.log_status(TaskStatus.RUNNING, "Copying the PDF to a subdirectory...")
    today = config.start_time.date().strftime("%Y-%m-%d")
    target_dir = pdf_path.parent.joinpath(f"{today} Sermon Slides")
    if target_dir.exists():
        raise ValueError(f"{target_dir} already exists")
    target_dir.mkdir()
    pdf_copy_path = target_dir.joinpath(target_dir.name)
    shutil.copy(src=pdf_path, dst=pdf_copy_path)

    num_dots = 3
    messenger.log_status(TaskStatus.RUNNING, "Generating PNGs" + "." * num_dots)
    command = [
        "pdftoppm",
        "-png",
        "-r",
        "300",
        "-progress",
        pdf_copy_path.as_posix(),
        target_dir.joinpath("slide").as_posix(),
    ]
    # https://stackoverflow.com/a/17698359
    with Popen(command, stderr=subprocess.PIPE, text=True, bufsize=1) as p:
        if p.stderr:
            for line in p.stderr:
                try:
                    fields = line.split()
                    done = int(fields[0])
                    total = int(fields[1])
                    messenger.log_status(
                        TaskStatus.RUNNING,
                        "Generating PNGs" + ("." * num_dots) + f" ({done}/{total})",
                    )
                except (IndexError, ValueError):
                    # Fall back to just changing the number of dots, to show some progress
                    num_dots = 1 + (num_dots % 3)
                    messenger.log_status(
                        TaskStatus.RUNNING, "Generating PNGs" + "." * num_dots
                    )
    messenger.log_status(TaskStatus.DONE, f"Slides generated in {target_dir.resolve()}")


def main(
    args: ConvertPdfToSlidesArgs,
    config: Config,
    dep: ReccDependencyProvider,
) -> None:
    tasks = TaskModel(
        name="convert_pdf_to_slides",
        description="An error occurred.",
        only_auto=True,
    )
    autochecklist.run(
        args=args,
        config=config,
        dependency_provider=dep,
        tasks=tasks,
        module=sys.modules[__name__],
    )


if __name__ == "__main__":
    args = ConvertPdfToSlidesArgs.parse(sys.argv)
    config = Config(args)
    msg = SimplifiedMessengerSettings(
        log_file=config.convert_pdf_to_slides_log,
        script_name="Convert PDF to Slides",
        description=args.DESCRIPTION,
        show_statuses_by_default=True,
    )
    dependency_provider = ReccDependencyProvider(
        args=args, config=config, messenger=msg
    )
    main(args, config, dependency_provider)
