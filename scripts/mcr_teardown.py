from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from messenger import Messenger
from pathlib import Path
from typing import List

from task import Task, TaskThread
import mcr_teardown_tasks


# TODO: Read tasks from a JSON file and automatically construct the threads. Each task has fields "name", "description", and "depends_on". The name must be a unique identifier and is used as the function name as well. The description serves as the fallback message. The dependencies are identified by name.
# TODO: Split MCR teardown checklist into manual and automated tasks. In the automated tasks section, add a reminder that, if someone changes the checklist, they should also create an issue to update the script (ideally make the change in the manual section at first?) Alternatively, add the manual tasks to the script and go directly to the "fallback" message.
# TODO: Save progress in a file in case the script needs to be stopped and restarted? It would probably be nice to create one or more classes to encapsulate this. Watch out for race conditions if only one class is used (maybe better to have one class per thread).
# TODO: Make it easier to kill the program
# TODO: Let tasks optionally include a verifier method that checks whether the step was completed properly
# TODO: Visualize task graph?


def main():
    args = _parse_args()

    messenger = _create_messenger(args.log_dir)

    rebroadcasts_thread = TaskThread(
        name="Rebroadcasts",
        tasks=[
            Task(
                mcr_teardown_tasks.create_rebroadcasts,
                f"Create rebroadcasts titled '{_get_rebroadcast_title()}' at {_join_list(_get_rebroadcast_times())}.",
                messenger,
            )
        ],
    )
    vimeo_thread = TaskThread(
        name="Vimeo",
        tasks=[
            Task(
                mcr_teardown_tasks.export_to_vimeo,
                "On BoxCast, export the recording to Vimeo.",
                messenger,
            ),
            Task(
                mcr_teardown_tasks.rename_video_on_vimeo,
                f"On Vimeo, rename the video to '{_get_vimeo_video_title(args.message_series, args.message_title)}'.",
                messenger,
            ),
        ],
    )
    captions_thread = TaskThread(
        name="Captions",
        tasks=[
            Task(
                mcr_teardown_tasks.start_generating_captions,
                "On BoxCast, press the button to start generating captions.",
                messenger,
            ),
            Task(
                mcr_teardown_tasks.publish_and_download_captions,
                f"On BoxCast, review low-confidence cues and publish the captions. Then download the captions and save them in '{_get_original_captions_filename()}'.",
                messenger,
            ),
            Task(
                mcr_teardown_tasks.remove_worship_captions,
                "Remove captions during worship.",
                messenger,
            ),
            Task(
                mcr_teardown_tasks.spell_check_captions,
                "If you want, quickly check the spelling of the captions.",
                messenger,
            ),
            Task(
                mcr_teardown_tasks.upload_captions_to_boxcast,
                "Upload the captions to BoxCast.",
                messenger,
            ),
        ],
    )
    vimeo_captions_thread = TaskThread(
        name="VimeoCaptions",
        tasks=[
            Task(
                mcr_teardown_tasks.upload_captions_to_vimeo,
                "Upload the captions to Vimeo and make sure they are enabled.",
                messenger,
            )
        ],
        prerequisites=[vimeo_thread, captions_thread],
    )

    rebroadcasts_thread.start()
    captions_thread.start()
    vimeo_thread.start()
    vimeo_captions_thread.start()

    rebroadcasts_thread.join()
    vimeo_captions_thread.join()
    # No need to wait for captions thread or Vimeo thread, since they are prerequisites

    messenger.close()


def _create_messenger(log_directory: Path) -> Messenger:
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = f"{log_directory}\\{current_date} {current_time} mcr_teardown.log"
    return Messenger(log_file)


def _parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Script to guide and automate the teardown process in the MCR."
    )

    # TODO: Check whether the values are the same as in the previous week?
    parser.add_argument(
        "-s",
        "--message-series",
        required=True,
        help="Name of the series to which today's sermon belongs.",
    )
    parser.add_argument(
        "-t", "--message-title", required=True, help="Title of today's sermon."
    )
    parser.add_argument(
        "-l",
        "--log-dir",
        type=_parse_directory,
        default="D:\\Users\\Tech\\Documents\\Logs",
    )

    args = parser.parse_args()

    if not args.log_dir.exists():
        raise ValueError()

    return args


def _parse_directory(path_str: str) -> Path:
    path = Path(path_str)

    if not path.exists():
        raise ArgumentTypeError(f"Path '{path_str}' does not exist.")
    if not path.is_dir():
        raise ArgumentTypeError(f"Path '{path_str}' is not a directory.")
    # TODO: Check whether the path is accessible?

    path = path.resolve()
    return path


def _get_rebroadcast_title() -> str:
    current_date = datetime.now().strftime("%B %d, %Y")
    return f"Sunday Gathering Rebroadcast: {current_date}"


def _get_rebroadcast_times() -> List[str]:
    return ["1:00 PM", "5:00 PM", "7:00 PM"]


def _get_vimeo_video_title(message_series: str, message_title: str) -> str:
    current_date = datetime.now().strftime("%Y-%m-%d")
    return f"{current_date} | {message_series} | {message_title}"


def _join_list(items: List[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    elif len(items) == 2:
        return f"{items[0]} and {items[1]}"
    else:
        return f"{', '.join(items[:-1])}, and {items[-1]}"


def _get_original_captions_filename():
    current_date = datetime.now().strftime("%Y-%m-%d")
    return f"D:\\Users\\Tech\\Documents\\Captions\\{current_date}\\original.vtt"


if __name__ == "__main__":
    main()
