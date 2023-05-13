from __future__ import annotations

import logging as log
from datetime import datetime
from threading import Thread
from typing import Callable, List

# TODO: Split MCR teardown checklist into manual and automated tasks. In the automated tasks section, add a reminder that, if someone changes the checklist, they should also create an issue to update the script (ideally make the change in the manual section at first?)
# TODO: Save progress in a file in case the script needs to be stopped and restarted? It would probably be nice to create one or more classes to encapsulate this. Watch out for race conditions if only one class is used (maybe better to have one class per thread).
# TODO: Set timeouts for tasks?


LOG_DIRECTORY = "D:\\Users\\Tech\\Documents\\Logs"
# LOG_DIRECTORY = "C:\\Users\\louis\\Projects\\Church\\recc-tech\\logs"


# region Threads


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
        log.debug(f"Running task '{self._run.__name__}'.")
        try:
            self._run()
            log.info(f"Task '{self._run.__name__}' completed successfully.")
        except Exception as e:
            log.debug(f"Task '{self._run.__name__}' failed with an exception: {e}")
            message = f"{self._fallback_message} When you are done, press ENTER."
            if not isinstance(e, NotImplementedError):
                message = f"Task '{self._run.__name__}' encountered an error. {message}"
            input(message)


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


# region Logging


def configure_logging():
    # Send detailed debug messages to the log file.
    date = datetime.now().strftime("%Y-%m-%d")
    time = datetime.now().strftime("%H-%M-%S")
    log_file = f"{LOG_DIRECTORY}\\{date} {time} mcr_teardown.log"
    file_handler = log.FileHandler(log_file)
    file_handler.setLevel(log.DEBUG)
    file_handler.setFormatter(
        log.Formatter(
            "[%(levelname)-8s] [%(threadName)-13s] [%(asctime)s] %(message)s",
            datefmt="%H:%M:%S",
        ),
    )

    # Send concise info messages to the console.
    console_handler = log.StreamHandler()
    console_handler.setLevel(log.INFO)
    console_handler.setFormatter(
        log.Formatter(
            "[%(levelname)-8s] [%(asctime)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root_logger = log.getLogger()
    root_logger.setLevel(log.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


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
    # TODO: Download VTT file
    raise NotImplementedError(
        "Publishing and downloading captions is not yet implemented."
    )


def remove_worship_captions():
    # TODO: Remove captions during worship (based on caption length?)
    # TODO: Have the user verify that the captions were removed as expected
    # TODO: Record which captions were removed by the user so that automatic removal of worship captions can be tested
    raise NotImplementedError("Removing worship captions is not yet implemented.")


def spell_check_captions():
    # TODO: Spell check captions (Whisper API?)
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


# region main


def main():
    configure_logging()

    rebroadcasts_thread = TaskThread(
        name="Rebroadcasts",
        tasks=[
            Task(
                create_rebroadcasts, "Create rebroadcasts titled '<TITLE>' at <TIMES>."
            )
        ],
    )
    vimeo_thread = TaskThread(
        name="Vimeo",
        tasks=[
            Task(export_to_vimeo, "On BoxCast, export the recording to Vimeo."),
            Task(rename_video_on_vimeo, "On Vimeo, rename the new video to '<TITLE>'."),
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
                "On BoxCast, review low-confidence cues and publish the captions. Then download the captions and save them in a file called '<FILE>'.",
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


if __name__ == "__main__":
    main()


# endregion
