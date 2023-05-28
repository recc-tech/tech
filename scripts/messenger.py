import logging
from collections import deque
from getpass import getpass
from logging import FileHandler, Handler, Logger, StreamHandler
from pathlib import Path
from threading import Lock, Semaphore, Thread
from typing import Any, Callable, Deque


class Messenger:
    """
    Thread-safe interface for logging to a file and to the console. Also allows for getting user input without having log messages appear in the console and without making logging blocking.
    """

    should_exit: bool

    file_logger: Logger
    console_logger: Logger

    console_queue: Deque[Callable[[], Any]]
    console_semaphore: Semaphore

    input_value: str

    def __init__(self, log_file: Path):
        self.should_exit = False

        if not log_file.exists():
            log_file.parent.mkdir(exist_ok=True, parents=True)

        # Send detailed debug messages to the log file
        self.file_logger = Messenger._initialize_logger(
            name="file_messenger",
            handler=FileHandler(log_file),
            level=logging.DEBUG,
            log_format="[%(levelname)-8s] [%(threadName)-25s] [%(asctime)s] %(message)s",
            date_format="%H:%M:%S",
        )

        # Send concise info messages to the console.
        self.console_logger = Messenger._initialize_logger(
            name="console_messenger",
            handler=StreamHandler(),
            level=logging.INFO,
            log_format="[%(levelname)-8s] [%(asctime)s] %(message)s",
            date_format="%H:%M:%S",
        )

        # Push tasks to a queue and have a dedicated thread handle those operations
        self.console_queue = deque()
        self.console_semaphore = Semaphore(0)
        self._start_thread(
            name="ConsoleMessenger",
            semaphore=self.console_semaphore,
            queue=self.console_queue,
        )

        # Use an instance variable to send user input between threads
        self.input_value = ""

    def log(self, level: int, message: str):
        self.log_separate(level, message, message)

    def log_separate(self, level: int, console_message: str, log_file_message: str):
        self.file_logger.log(level=level, msg=log_file_message)

        self.console_queue.append(
            lambda: self.console_logger.log(level=level, msg=console_message)
        )
        # Signal that there is a task in the queue
        self.console_semaphore.release()

    def input(self, prompt: str) -> str:
        return self._get_input(prompt, input)

    def get_password(self, prompt: str) -> str:
        return self._get_input(prompt, getpass)

    def _get_input(self, prompt: str, input_func: Callable[[str], str]) -> str:
        # Use a lock so that this function blocks until the task has run
        lock = Lock()
        lock.acquire()

        def input_task():
            self.input_value = input_func(prompt)
            lock.release()

        self.console_queue.append(input_task)
        # Signal that there is a task in the queue
        self.console_semaphore.release()

        # Wait for the task to be done
        lock.acquire()

        return self.input_value

    def close(self):
        self.should_exit = True
        # Pretend there's one more entry in each queue to get the threads to exit
        self.console_semaphore.release()

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

    def _start_thread(
        self, name: str, semaphore: Semaphore, queue: Deque[Callable[[], Any]]
    ):
        def console_tasks_thread():
            while True:
                # Wait for there to be a task in the queue
                semaphore.acquire()

                # Exit only once the queue is empty
                if self.should_exit and len(queue) == 0:
                    return

                task = queue.popleft()
                task()

        Thread(target=console_tasks_thread, name=name).start()
