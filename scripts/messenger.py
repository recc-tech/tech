import logging
from collections import deque
from getpass import getpass
from logging import FileHandler, Handler, StreamHandler
from pathlib import Path
from threading import Lock, Semaphore, Thread
from typing import Any, Callable, Deque


class BaseMessenger:
    def log(self, level: int, message: str) -> None:
        """
        Logs the given message. For example, this might save the message to a file or display it in the console.
        """
        raise NotImplementedError()

    def close(self):
        """
        Performs any cleanup that is required before exiting (e.g., making worker threads exit).
        """
        pass

    @staticmethod
    def _initialize_logger(
        name: str, handler: Handler, level: int, log_format: str, date_format: str
    ):
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter(
                fmt=log_format,
                datefmt=date_format,
            ),
        )
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        return logger


class FileMessenger(BaseMessenger):
    def __init__(self, log_file: Path):
        if not log_file.exists():
            log_file.parent.mkdir(exist_ok=True, parents=True)

        self.file_logger = BaseMessenger._initialize_logger(
            name="file_messenger",
            handler=FileHandler(log_file),
            level=logging.DEBUG,
            log_format="[%(levelname)-8s] [%(threadName)-25s] [%(asctime)s] %(message)s",
            date_format="%H:%M:%S",
        )

    def log(self, level: int, message: str):
        self.file_logger.log(level=level, msg=message)


class InputMessenger(BaseMessenger):
    def input(self, prompt: str, input_func: Callable[[str], str]) -> str:
        """
        Takes user input using the given function. For example, you can take regular input using `input_func=input`
        and take passwords using `input_func=getpass`.
        """
        raise NotImplementedError()


class ConsoleMessenger(InputMessenger):
    # TODO: Make the logs look nicer (e.g., only the latest message from each thread? add colour?)

    def __init__(self):
        self._should_exit = False

        self._console_logger = BaseMessenger._initialize_logger(
            name="console_messenger",
            handler=StreamHandler(),
            level=logging.INFO,
            log_format="[%(levelname)-8s] [%(asctime)s] %(message)s",
            date_format="%H:%M:%S",
        )

        # Push tasks to a queue and have a dedicated thread handle those operations
        self._console_queue: Deque[Callable[[], Any]] = deque()
        self._console_semaphore = Semaphore(0)
        self._start_thread(
            name="ConsoleMessenger",
            semaphore=self._console_semaphore,
            queue=self._console_queue,
        )

        # Use an instance variable to send user input between threads
        self._input_value = ""

    def log(self, level: int, message: str) -> None:
        self._console_queue.append(
            lambda: self._console_logger.log(level=level, msg=message)
        )
        # Signal that there is a task in the queue
        self._console_semaphore.release()

    def input(self, prompt: str, input_func: Callable[[str], str]) -> str:
        # Use a lock so that this function blocks until the task has run
        lock = Lock()
        lock.acquire()

        def input_task():
            self._input_value = input_func(prompt)
            lock.release()

        self._console_queue.append(input_task)
        # Signal that there is a task in the queue
        self._console_semaphore.release()

        # Wait for the task to be done
        lock.acquire()

        return self._input_value

    def close(self):
        self._should_exit = True
        # Pretend there's one more entry in the queue to get the threads to exit
        self._console_semaphore.release()

    def _start_thread(
        self, name: str, semaphore: Semaphore, queue: Deque[Callable[[], Any]]
    ):
        def console_tasks_thread():
            while True:
                # Wait for there to be a task in the queue
                semaphore.acquire()

                # Exit only once the queue is empty
                if self._should_exit and len(queue) == 0:
                    return

                task = queue.popleft()
                task()

        Thread(target=console_tasks_thread, name=name).start()


class TkMessenger(InputMessenger):
    # TODO: Implement this as an alternative to the ConsoleMessenger
    ...


class Messenger:
    """
    Thread-safe interface for logging to a file and to the console. Also allows for getting user input without having log messages appear in the console and without making logging blocking.
    """

    def __init__(
        self, file_messenger: FileMessenger, console_messenger: ConsoleMessenger
    ):
        self._file_messenger = file_messenger
        self._console_messenger = console_messenger

    def log(self, level: int, message: str):
        self.log_separate(level, message, message)

    def log_separate(self, level: int, console_message: str, log_file_message: str):
        self._file_messenger.log(level, log_file_message)
        self._console_messenger.log(level, console_message)

    def input(self, prompt: str) -> str:
        return self._console_messenger.input(prompt, input)

    def get_password(self, prompt: str) -> str:
        return self._console_messenger.input(prompt, getpass)

    def close(self):
        self._file_messenger.close()
        self._console_messenger.close()
