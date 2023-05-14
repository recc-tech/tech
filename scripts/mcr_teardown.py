from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from logging import DEBUG, INFO, WARN
from messenger import Messenger
from pathlib import Path
from threading import Thread
from typing import Callable, List

# TODO: Split MCR teardown checklist into manual and automated tasks. In the automated tasks section, add a reminder that, if someone changes the checklist, they should also create an issue to update the script (ideally make the change in the manual section at first?)
# TODO: Save progress in a file in case the script needs to be stopped and restarted? It would probably be nice to create one or more classes to encapsulate this. Watch out for race conditions if only one class is used (maybe better to have one class per thread).
# TODO: Make it easier to kill the program


messenger: Messenger


# region Thread and task classes


class Task:
    """
    Represents a single, independent task.
    """

    _run: Callable[[], None]
    """
    Function which performs the given task, but without logging or exception handling.
    """

    _fallback_message: str
    """
    Instructions to show to the user in case the function raises an exception.
    """

    def __init__(self, func: Callable[[], None], fallback_message: str):
        self._run = func
        self._fallback_message = fallback_message

    def run(self):
        messenger.log(DEBUG, f"Running task '{self._run.__name__}'.")
        try:
            self._run()
            messenger.log(INFO, f"Task '{self._run.__name__}' completed successfully.")
        except Exception as e:
            if isinstance(e, NotImplementedError):
                messenger.log(
                    DEBUG,
                    f"Task '{self._run.__name__}' is not yet implemented. Requesting user input.",
                )
            else:
                messenger.log(
                    WARN,
                    f"Task '{self._run.__name__}' failed with an exception: {e}",
                )

            message = f"{self._fallback_message} When you are done, press ENTER."
            if not isinstance(e, NotImplementedError):
                message = f"Task '{self._run.__name__}' encountered an error. {message}"
            messenger.wait_for_input(message)


class TaskThread(Thread):
    """
    Represents a sequence of tasks.
    """

    def __init__(
        self,
        name: str,
        tasks: List[Task],
        prerequisites: List[TaskThread] = [],
    ):
        if not tasks:
            raise ValueError("A thread must have at least one task to perform.")
        self.tasks = tasks
        self.prerequisites = prerequisites
        super().__init__(name=name)

    def run(self):
        # Wait for prerequisites
        for p in self.prerequisites:
            p.join()

        # Run tasks
        for t in self.tasks:
            t.run()


# endregion


# region Rebroadcasts thread


def create_rebroadcasts():
    # TODO: Create rebroadcast
    raise NotImplementedError("Creating rebroadcasts is not yet implemented.")


# endregion


# region Vimeo thread


def export_to_vimeo():
    # TODO: Export to Vimeo
    raise NotImplementedError("Exporting to Vimeo is not yet implemented.")


def rename_video_on_vimeo():
    # TODO: Go to Vimeo and rename video
    raise NotImplementedError("Renaming the video in Vimeo is not yet implemented.")


# endregion


# region Captions thread


def start_generating_captions():
    # TODO: Press the button to start generating captions (if it hasn't already started)
    raise NotImplementedError("Starting to generate captions is not yet implemented.")


def publish_and_download_captions():
    # TODO: Record low-confidence cues (save to file)
    # TODO: Publish captions
    # TODO: Download VTT file to original.vtt
    raise NotImplementedError(
        "Publishing and downloading captions is not yet implemented."
    )


def copy_captions():
    # TODO: Copy original.vtt to without_worship.vtt
    raise NotImplementedError(
        "Copying captions file to 'without_worship.vtt' is not yet implemented."
    )


def remove_worship_captions():
    # TODO: Remove captions during worship (based on caption length?)
    # TODO: Have the user verify that the captions were removed as expected
    # TODO: Record which captions were removed by the user so that automatic removal of worship captions can be tested
    raise NotImplementedError("Removing worship captions is not yet implemented.")


def spell_check_captions():
    # TODO: Spell check captions (Whisper API?)
    # TODO: Save results in final.vtt
    raise NotImplementedError("Spell check is not yet implemented.")


def upload_captions_to_boxcast():
    # TODO: Upload to BoxCast
    raise NotImplementedError("Uploading captions to BoxCast is not yet implemented.")


# endregion


# region Vimeo captions thread


def upload_captions_to_vimeo():
    # TODO: Upload captions to Vimeo
    raise NotImplementedError("Uploading captions to Vimeo is not yet implemented.")


# endregion


# region Main


def main():
    global messenger

    args = _parse_args()

    messenger = _create_messenger(args.log_dir)

    rebroadcasts_thread = TaskThread(
        name="Rebroadcasts",
        tasks=[
            Task(
                create_rebroadcasts,
                f"Create rebroadcasts titled '{_get_rebroadcast_title()}' at {_join_list(_get_rebroadcast_times())}.",
            )
        ],
    )
    vimeo_thread = TaskThread(
        name="Vimeo",
        tasks=[
            Task(export_to_vimeo, "On BoxCast, export the recording to Vimeo."),
            Task(
                rename_video_on_vimeo,
                f"On Vimeo, rename the video to '{_get_vimeo_video_title(args.message_series, args.message_title)}'.",
            ),
        ],
    )
    captions_thread = TaskThread(
        name="Captions",
        tasks=[
            Task(
                start_generating_captions,
                "On BoxCast, press the button to start generating captions.",
            ),
            Task(
                publish_and_download_captions,
                f"On BoxCast, review low-confidence cues and publish the captions. Then download the captions and save them in '{_get_original_captions_filename()}'.",
            ),
            Task(remove_worship_captions, "Remove captions during worship."),
            Task(
                spell_check_captions,
                "If you want, quickly check the spelling of the captions.",
            ),
            Task(upload_captions_to_boxcast, "Upload the captions to BoxCast."),
        ],
    )
    vimeo_captions_thread = TaskThread(
        name="VimeoCaptions",
        tasks=[
            Task(
                upload_captions_to_vimeo,
                "Upload the captions to Vimeo and make sure they are enabled.",
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


# endregion
