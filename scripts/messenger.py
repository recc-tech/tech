import ctypes
import logging
import threading
from collections import deque
from datetime import datetime
from enum import Enum
from getpass import getpass
from logging import FileHandler, Handler, StreamHandler
from pathlib import Path
from threading import Lock, Semaphore, Thread
from tkinter import Misc, Text, Tk, messagebox, simpledialog
from tkinter.ttk import Button, Frame, Style
from typing import Any, Callable, Deque, Dict, Union


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARN = logging.WARN
    ERROR = logging.ERROR
    FATAL = logging.FATAL

    def __str__(self):
        return self.name


class BaseMessenger:
    def log(self, level: LogLevel, message: str) -> None:
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


class InputMessenger(BaseMessenger):
    def input(self, prompt: str) -> Union[str, None]:
        raise NotImplementedError()

    def input_password(self, prompt: str) -> Union[str, None]:
        raise NotImplementedError()

    def wait(self, prompt: str) -> None:
        raise NotImplementedError()

    def shutdown_requested(self) -> bool:
        """
        Whether the user wants to cancel the program (e.g., by closing the GUI or by hitting CTRL+C).
        """
        raise NotImplementedError()


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

    def log(self, level: LogLevel, message: str):
        self.file_logger.log(level=level.value, msg=message)


class ConsoleMessenger(InputMessenger):
    # TODO: Make the logs look nicer (e.g., only the latest message from each thread? add colour?)

    def __init__(self):
        self._should_exit = False
        self._shutdown_requested = False

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

    def log(self, level: LogLevel, message: str) -> None:
        self._console_queue.append(
            lambda: self._console_logger.log(level=level.value, msg=message)
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

    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

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
                # CTRL+C causes an EOFError if the program was waiting for input
                # The KeyboardInterrupt should also be raised in the main thread, so no need to display anything here
                # TODO: Finish any remaining output tasks?
                try:
                    task()
                except (EOFError, KeyboardInterrupt):
                    self._shutdown_requested = True
                    return

        Thread(target=console_tasks_thread, name=name, daemon=True).start()

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


class CopyableText(Text):
    """
    Text widget that supports both text wrapping and copying its contents to the clipboard.
    """

    def __init__(self, parent: Misc, *args: Any, **kwargs: Any):
        super().__init__(
            parent,
            height=1,
            wrap="word",
            state="disabled",
            bg="#EEEEEE",
            highlightthickness=0,
            borderwidth=0,
            *args,
            **kwargs,
        )

    def set_text(self, text: str):
        # If you don't call update_idletasks(), the GUI seems to be confused and rows added later will be all over
        # the place
        root = self.winfo_toplevel()
        root.update_idletasks()

        self.config(state="normal")
        self.delete(1.0, "end")
        self.insert(1.0, text)
        self.config(state="disabled")

        # Adjust the text box height
        # https://stackoverflow.com/a/46100295
        height = self.tk.call((self, "count", "-update", "-displaylines", "1.0", "end"))
        self.configure(height=height)


class ThreadStatusFrame(Frame):
    _WIDTH_TO_WRAPLENGTH = 7.5

    _FONT = "Calibri 12"
    _BOLD_FONT = f"{_FONT} bold"

    def __init__(self, parent: Misc, thread_name: str):
        super().__init__(parent, padding=5)

        self._name = thread_name
        self._semaphore: Semaphore

        style = Style()
        style.configure("TButton", font=self._FONT)  # type: ignore

        self._button = Button(
            self,
            text="Done",
            command=lambda: self._semaphore.release(),
            state="disabled",
        )
        self._button.grid(row=0, column=0)

        self._name_label = CopyableText(
            self,
            width=35,
            font=self._FONT,
        )
        self._name_label.grid(row=0, column=1)
        self._name_label.set_text(thread_name)

        self._time_label = CopyableText(
            self,
            width=10,
            font=self._FONT,
        )
        self._time_label.grid(row=0, column=2)

        self._level_label = CopyableText(
            self,
            width=10,
            font=self._BOLD_FONT,
        )
        self._level_label.grid(row=0, column=3)

        self._message_label = CopyableText(self, width=100, font=self._FONT)
        self._message_label.grid(row=0, column=4)

    def update_contents(self, time: datetime, level: LogLevel, message: str):
        self._time_label.set_text(time.strftime("%H:%M:%S"))
        self._level_label.set_text(str(level))
        self._level_label.config(foreground=self._log_level_colour(level))
        self._message_label.set_text(message)

    def enable_button(self, semaphore: Semaphore):
        self._semaphore = semaphore
        self._button.config(state="enabled")

    def disable_button(self):
        self._button.config(state="disabled")

    @staticmethod
    def _log_level_colour(level: LogLevel) -> str:
        if level == LogLevel.DEBUG:
            return "#888888"
        elif level == LogLevel.INFO:
            return "#0000FF"
        elif level == LogLevel.WARN:
            return "#FF8800"
        elif level == LogLevel.ERROR:
            return "#FF0000"
        elif level == LogLevel.FATAL:
            return "#880000"
        else:
            return "#000000"


class TkMessenger(InputMessenger):
    def __init__(self):
        # TODO: Add a "header" text box with general instructions (and a goodbye message when the program is done?)

        self._shutdown_requested = False
        self._lock = Lock()
        self._thread_frame: Dict[int, ThreadStatusFrame] = {}

        root_started = Semaphore(0)
        self._gui_thread = Thread(
            name="GUI", target=lambda: self._run_gui(root_started)
        )
        self._gui_thread.start()
        # Wait for the GUI to enter the main loop
        root_started.acquire()

    def log(self, level: LogLevel, message: str):
        # TODO: What if the shutdown happens while in the middle of logging something?
        if self._shutdown_requested:
            return

        if not self._should_log(level):
            return

        # TODO: Is it safe to just update the GUI directly? Would it be better to use after()?
        # The tkinter docs seem to imply it is: https://docs.python.org/3/library/tkinter.html#threading-model
        ident = threading.get_ident()
        with self._lock:
            # TODO: thread identifier can be reused, so either remove old threads or generate my own identifiers
            if ident not in self._thread_frame:
                self._thread_frame[ident] = self._add_row()
            frame = self._thread_frame[ident]
        frame.update_contents(datetime.now(), level, message)

    def input(self, prompt: str, title: str = "") -> Union[str, None]:
        return simpledialog.askstring(title=title, prompt=prompt, show="*")

    def input_password(self, prompt: str, title: str = "") -> Union[str, None]:
        return simpledialog.askstring(title=title, prompt=prompt, show="*")

    def wait(self, prompt: str):
        if self._shutdown_requested:
            return

        semaphore = Semaphore(0)
        ident = threading.get_ident()
        with self._lock:
            if ident not in self._thread_frame:
                self._thread_frame[ident] = self._add_row()
            frame = self._thread_frame[ident]
        # TODO: Handle this better
        frame.update_contents(datetime.now(), LogLevel.INFO, prompt)
        frame.enable_button(semaphore)

        semaphore.acquire()

        # TODO: What if another thread modifies the frame somehow in between these two locks?
        with self._lock:
            frame.disable_button()

    def close(self):
        # Leave the GUI open until the user closes the window
        pass

    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def _close(self):
        # TODO: Release waiting threads?
        self._shutdown_requested = True
        # For some reason, using destroy() instead of quit() causes an error
        self._root.quit()

    def _run_gui(self, root_started: Semaphore):
        # Try to make the GUI less blurry
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

        self._root = Tk()
        self._root.title("MCR Teardown")
        self._root.geometry("3500x1600+0+0")
        self._root.protocol("WM_DELETE_WINDOW", self._confirm_exit)

        self._root.after(0, lambda: root_started.release())
        self._root.mainloop()

    def _confirm_exit(self):
        should_exit = messagebox.askyesno(  # type: ignore
            title="Confirm exit", message="Are you sure you want to exit?"
        )
        if should_exit:
            self._close()

    def _add_row(self) -> ThreadStatusFrame:
        frame = ThreadStatusFrame(self._root, threading.current_thread().name)
        frame.grid()
        return frame

    def _should_log(self, level: LogLevel) -> bool:
        """
        Decide whether the given message should be displayed in the GUI.
        """
        return level.value >= LogLevel.INFO.value


class Messenger:
    """
    Thread-safe interface for logging to a file and to the console. Also allows for getting user input without having log messages appear in the console and without making logging blocking.
    """

    def __init__(self, file_messenger: FileMessenger, input_messenger: InputMessenger):
        self._file_messenger = file_messenger
        self._input_messenger = input_messenger

    def log(self, level: LogLevel, message: str):
        self.log_separate(level, message, message)

    def log_separate(
        self, level: LogLevel, console_message: str, log_file_message: str
    ):
        self._file_messenger.log(level, log_file_message)
        self._input_messenger.log(level, console_message)

    def input(self, prompt: str) -> Union[str, None]:
        return self._input_messenger.input(prompt)

    def input_password(self, prompt: str) -> Union[str, None]:
        return self._input_messenger.input_password(prompt)

    def wait(self, prompt: str):
        self._input_messenger.wait(prompt)

    def close(self):
        # Close the input messenger first so that any new logs are still written to the file messenger
        self._input_messenger.close()
        self._file_messenger.close()

    def shutdown_requested(self) -> bool:
        return self._input_messenger.shutdown_requested()
