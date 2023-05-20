from __future__ import annotations

import logging
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from pathlib import Path

from config import Config
from messenger import Messenger
from task import TaskGraph

# TODO: Also let user specify priority (e.g., so manual tasks are done first?)
# TODO: Split MCR teardown checklist into manual and automated tasks. In the automated tasks section, add a reminder that, if someone changes the checklist, they should also create an issue to update the script (ideally make the change in the manual section at first?) Alternatively, add the manual tasks to the script and go directly to the "fallback" message.
# TODO: Save progress in a file in case the script needs to be stopped and restarted? It would probably be nice to create one or more classes to encapsulate this. Watch out for race conditions if only one class is used (maybe better to have one class per thread).
# TODO: Make it easier to kill the program
# TODO: Let tasks optionally include a verifier method that checks whether the step was completed properly
# TODO: Visualize task graph?
# TODO: Use ANSI escape sequences to move the cursor around, show status of all threads. Or would it be better to use the terminal only for input and output current status of each thread in a file?
# TODO: Make Messenger methods static so I can access them from anywhere without needing to pass the object around?
# TODO: Close down Messenger properly in the event of an exception


def main():
    args = _parse_args()

    config = Config(
        home_dir=args.home_dir,
        message_series=args.message_series,
        message_title=args.message_title,
    )

    messenger = _create_messenger(config.log_dir)

    try:
        task_file = Path(__file__).parent.joinpath("mcr_teardown_tasks.json")
        task_graph = TaskGraph.load(
            task_file=task_file,
            config=config,
            messenger=messenger,
        )
    except Exception as e:
        messenger.log(logging.FATAL, f"Failed to load task graph: {e}")
        messenger.close()
        return

    try:
        task_graph.start()
        task_graph.join()
    except Exception as e:
        messenger.log(logging.FATAL, f"Failed to run task graph: {e}")
    finally:
        messenger.close()


def _create_messenger(log_directory: Path) -> Messenger:
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H-%M-%S")
    log_file = log_directory.joinpath(f"{current_date} {current_time} mcr_teardown.log")
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
        "-d",
        "--home-dir",
        type=_parse_directory,
        default="D:\\Users\\Tech\\Documents",
    )

    return parser.parse_args()


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
    main()
