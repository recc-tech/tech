import logging
import threading
from collections import deque
from datetime import datetime
from getpass import getpass
from logging import FileHandler, Handler, StreamHandler
from pathlib import Path
from threading import Lock, Semaphore, Thread
from tkinter import Misc, StringVar, Tk, simpledialog
from tkinter.ttk import Button, Frame, Label
from typing import Any, Callable, Deque, Dict, Union


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
    def input(self, prompt: str) -> Union[str, None]:
        raise NotImplementedError()

    def input_password(self, prompt: str) -> Union[str, None]:
        raise NotImplementedError()

    def wait(self, prompt: str) -> None:
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

    def input(self, prompt: str) -> str:
        return self._input(prompt, input)

    def input_password(self, prompt: str) -> str:
        return self._input(prompt, getpass)

    def wait(self, prompt: str):
        prompt = prompt.strip()
        prompt = prompt if prompt.endswith(".") else f"{prompt}."
        prompt = f"- {prompt}"
        self.input(f"{prompt} When you are done, press ENTER.")

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

    def _input(self, prompt: str, input_func: Callable[[str], str]) -> str:
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


class ThreadStatusFrame(Frame):
    # TODO: Use an enum for log level?
    def __init__(self, parent: Misc, thread_name: str):
        super().__init__(parent, padding=5)

        self._name = thread_name
        self._name_label = Label(self, text=thread_name)
        self._name_label.grid(row=0, column=0)

        self._time_var = StringVar()
        self._time_label = Label(self, textvariable=self._time_var)
        self._time_label.grid(row=0, column=1)

        self._level_var = StringVar()
        self._level_label = Label(self, textvariable=self._level_var)
        self._level_label.grid(row=0, column=2)

        self._message_var = StringVar()
        self._message_label = Label(self, textvariable=self._message_var)
        self._message_label.grid(row=0, column=3)

        self._button: Union[None, Button] = None

    def update_contents(self, time: datetime, level: int, message: str):
        self._time_var.set(time.strftime("%H:%M:%S"))
        self._level_var.set(str(level))
        self._message_var.set(message)

    def add_button(self, text: str, command: Callable[[], None]):
        if self._button is not None:
            raise ValueError(
                f"Cannot add button: there is already a button in the frame for thread '{self._name}'."
            )
        self._button = Button(self, text=text, command=command)
        self._button.grid(row=0, column=4)

    def remove_button(self):
        if self._button is None:
            raise ValueError(
                f"Cannot remove button: there is no button in the frame for thread '{self._name}'."
            )
        self._button.destroy()
        self._button = None


class TkMessenger(InputMessenger):
    def __init__(self):
        self._lock = Lock()

        self._thread_frame: Dict[int, ThreadStatusFrame] = {}

        root_started = Semaphore(0)
        self._gui_thread = Thread(
            name="GUI", target=lambda: self._run_gui(root_started), daemon=True
        )
        self._gui_thread.start()
        # Wait for the GUI to enter the main loop
        root_started.acquire()

    def log(self, level: int, message: str):
        # TODO: Is it safe to just update the GUI directly? Would it be better to use after()?
        # The tkinter docs seem to imply it is: https://docs.python.org/3/library/tkinter.html#threading-model
        ident = threading.get_ident()
        with self._lock:
            if ident not in self._thread_frame:
                self._thread_frame[ident] = self._add_row()
            frame = self._thread_frame[ident]
        frame.update_contents(datetime.now(), level, message)

    def input(self, prompt: str, title: str = "") -> Union[str, None]:
        return simpledialog.askstring(title=title, prompt=prompt, show="*")

    def input_password(self, prompt: str, title: str = "") -> Union[str, None]:
        return simpledialog.askstring(title=title, prompt=prompt, show="*")

    def wait(self, prompt: str):
        semaphore = Semaphore(0)
        command = lambda: semaphore.release()
        ident = threading.get_ident()
        with self._lock:
            if ident not in self._thread_frame:
                self._thread_frame[ident] = self._add_row()
            frame = self._thread_frame[ident]
        # TODO: Handle this better
        frame.update_contents(datetime.now(), logging.INFO, prompt)
        frame.add_button(text="Done", command=command)

        semaphore.acquire()

        # TODO: What if another thread modifies the frame somehow in between these two locks?
        with self._lock:
            frame.remove_button()

    def close(self):
        # It seems the program will hang if root.destroy() is called from outside the GUI thread
        self._root.after(0, self._root.destroy)

    def _run_gui(self, root_started: Semaphore):
        self._root = Tk()
        self._root.title("MCR Teardown")
        self._root.geometry("1024x512+0+0")

        self._root.after(0, lambda: root_started.release())
        self._root.mainloop()

    def _add_row(self) -> ThreadStatusFrame:
        frame = ThreadStatusFrame(
            self._root,
            threading.current_thread().name,
        )
        frame.grid()
        return frame


class Messenger:
    """
    Thread-safe interface for logging to a file and to the console. Also allows for getting user input without having log messages appear in the console and without making logging blocking.
    """

    def __init__(
        self, file_messenger: FileMessenger, input_messenger: InputMessenger
    ):
        self._file_messenger = file_messenger
        self._input_messenger = input_messenger

    def log(self, level: int, message: str):
        self.log_separate(level, message, message)

    def log_separate(self, level: int, console_message: str, log_file_message: str):
        self._file_messenger.log(level, log_file_message)
        self._input_messenger.log(level, console_message)

    def input(self, prompt: str) -> Union[str, None]:
        return self._input_messenger.input(prompt)

    def input_password(self, prompt: str) -> Union[str, None]:
        return self._input_messenger.input_password(prompt)

    def wait(self, prompt: str):
        self._input_messenger.wait(prompt)

    def close(self):
        self._file_messenger.close()
        self._input_messenger.close()
