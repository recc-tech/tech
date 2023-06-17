import ctypes
import logging
from collections import deque
from datetime import datetime
from enum import Enum
from getpass import getpass
from logging import FileHandler, Handler, StreamHandler
from pathlib import Path
from threading import Event, Lock, Semaphore, Thread
from tkinter import Canvas, Misc, Text, Tk, messagebox, simpledialog
from tkinter.ttk import Button, Frame, Scrollbar, Style
from typing import Any, Callable, Deque, Dict, Union


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARN = logging.WARN
    ERROR = logging.ERROR
    FATAL = logging.FATAL

    def __str__(self):
        return self.name


class InputMessenger:
    def log(self, task_name: str, level: LogLevel, message: str) -> None:
        """
        Logs the given message. For example, this might save the message to a file or display it in the console.
        """
        raise NotImplementedError()

    def close(self):
        """
        Performs any cleanup that is required before exiting (e.g., making worker threads exit).
        """
        pass

    def input(self, prompt: str) -> Union[str, None]:
        raise NotImplementedError()

    def input_password(self, prompt: str) -> Union[str, None]:
        raise NotImplementedError()

    def wait(self, task_name: str, prompt: str) -> None:
        raise NotImplementedError()

    def shutdown_requested(self) -> bool:
        """
        Whether the user wants to cancel the program (e.g., by closing the GUI or by hitting CTRL+C).
        """
        raise NotImplementedError()


class FileMessenger:
    def __init__(self, log_file: Path):
        if not log_file.exists():
            log_file.parent.mkdir(exist_ok=True, parents=True)

        self.file_logger = _initialize_logger(
            name="file_messenger",
            handler=FileHandler(log_file),
            level=logging.DEBUG,
            log_format="[%(levelname)-8s] [%(asctime)s] %(message)s",
            date_format="%H:%M:%S",
        )

    def log(self, task_name: str, level: LogLevel, message: str):
        self.file_logger.log(level=level.value, msg=f"[{task_name:<35}] {message}")


class ConsoleMessenger(InputMessenger):
    # TODO: Make the logs look nicer (e.g., only the latest message from each thread? add colour?)

    def __init__(self, description: str):
        print(f"{description}\n\n")

        self._should_exit = False
        self._shutdown_requested = False

        self._console_logger = _initialize_logger(
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

    def log(self, task_name: str, level: LogLevel, message: str) -> None:
        self._console_queue.append(
            lambda: self._console_logger.log(
                level=level.value, msg=f"[{task_name}] message"
            )
        )
        # Signal that there is a task in the queue
        self._console_semaphore.release()

    def input(self, prompt: str) -> str:
        return self._input(prompt, input)

    def input_password(self, prompt: str) -> str:
        return self._input(prompt, getpass)

    def wait(self, task_name: str, prompt: str):
        prompt = prompt.strip()
        prompt = prompt if prompt.endswith(".") else f"{prompt}."
        prompt = f"- [{task_name}] {prompt}"
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


class ScrollableFrame(Frame):
    def __init__(self, parent: Misc, *args: Any, **kwargs: Any):
        # TODO: The fact that this widget places itself is pretty sketchy

        outer_frame = Frame(parent)
        outer_frame.pack(fill="both", expand=1)

        scrollbar = Scrollbar(outer_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self._canvas = Canvas(
            outer_frame,
            yscrollcommand=scrollbar.set,
            borderwidth=0,
            highlightthickness=0,
        )
        self._canvas.pack(side="left", fill="both", expand=1)
        self._canvas.bind(
            "<Configure>",
            lambda e: self.update_scrollregion(),
        )
        scrollbar.config(command=self._canvas.yview)  # type: ignore

        # Allow scrolling with the mouse (why does this not work out of the box? D:<<)
        self._root = parent.winfo_toplevel()
        self._root.bind_all(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )

        if "padding" not in kwargs:
            kwargs["padding"] = 25
        super().__init__(self._canvas, *args, **kwargs)
        self._canvas.create_window((0, 0), window=self, anchor="nw")

        # To avoid race conditions, use a separate thread to update the scroll region
        self._update_scrollregion = Event()
        scrollregion_updates_thread = Thread(
            name="ScrollregionUpdates",
            target=self._run_scrollregion_updates_thread,
            daemon=True,
        )
        scrollregion_updates_thread.start()

    def update_scrollregion(self):
        self._update_scrollregion.set()

    def _run_scrollregion_updates_thread(self):
        while True:
            self._update_scrollregion.wait()
            self._update_scrollregion.clear()
            # Make sure the display has updated before recomputing the scrollregion size
            self._root.update_idletasks()
            region = self._canvas.bbox("all")
            self._canvas.config(scrollregion=region)


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


class TaskStatusFrame(Frame):
    _PADX = 5
    _LOG_LEVEL_COLOUR = {
        LogLevel.DEBUG: "#888888",
        LogLevel.INFO: "#0000FF",  # "#0000FF"
        LogLevel.WARN: "#FF9900",
        LogLevel.ERROR: "#FF0000",
        LogLevel.FATAL: "#990000",
    }
    _DEFAULT_LOG_LEVEL_COLOUR = "#FFFFFF"

    def __init__(
        self,
        parent: Misc,
        task_name: str,
        log_time: datetime,
        level: LogLevel,
        message: str,
        font: str,
        padding: int,
        background: str,
        foreground: str,
    ):
        super().__init__(parent, padding=padding)

        self._name = task_name

        self._level_label = CopyableText(
            self, width=10, font=font, background=background, foreground=foreground
        )
        self._level_label.grid(row=0, column=0, padx=self._PADX)

        self._time_label = CopyableText(
            self, width=10, font=font, background=background, foreground=foreground
        )
        self._time_label.grid(row=0, column=1, padx=self._PADX)

        self._name_label = CopyableText(
            self, width=35, font=font, background=background, foreground=foreground
        )
        self._name_label.grid(row=0, column=2, padx=self._PADX)
        self._name_label.set_text(task_name)

        self._message_label = CopyableText(
            self, width=100, font=font, background=background, foreground=foreground
        )
        self._message_label.grid(row=0, column=3, padx=self._PADX)

        self.update_contents(log_time, level, message)

    def update_contents(self, time: datetime, level: LogLevel, message: str):
        self._time_label.set_text(time.strftime("%H:%M:%S"))
        self._level_label.set_text(str(level))
        self._level_label.config(foreground=self._log_level_colour(level))
        self._message_label.set_text(message)

    @staticmethod
    def _log_level_colour(level: LogLevel) -> str:
        return (
            TaskStatusFrame._LOG_LEVEL_COLOUR[level]
            if level in TaskStatusFrame._LOG_LEVEL_COLOUR
            else TaskStatusFrame._DEFAULT_LOG_LEVEL_COLOUR
        )


class ActionItemFrame(Frame):
    _PADX = 5

    def __init__(
        self,
        parent: Misc,
        task_name: str,
        prompt: str,
        font: str,
        background: str,
        foreground: str,
        padding: int,
        **kwargs: Any,
    ):
        super().__init__(parent, padding=padding, **kwargs)

        self._lock = Lock()
        self._lock.acquire()

        self._button = Button(
            self,
            text="Done",
            command=self._handle_click,
            state="enabled",
        )
        self._button.grid(row=0, column=0, padx=self._PADX)

        self._name_label = CopyableText(
            self, width=35, font=font, background=background, foreground=foreground
        )
        self._name_label.grid(row=0, column=1, padx=self._PADX)
        self._name_label.set_text(task_name)

        self._message_label = CopyableText(
            self, width=100, font=font, background=background, foreground=foreground
        )
        self._message_label.grid(row=0, column=2, padx=self._PADX)
        self._message_label.set_text(prompt)

    def wait_for_click(self):
        self._lock.acquire()

    def _handle_click(self):
        self._lock.release()
        self.destroy()


class TkMessenger(InputMessenger):
    _BACKGROUND_COLOUR = "#EEEEEE"
    _FOREGROUND_COLOUR = "#000000"

    _NORMAL_FONT = "Calibri 12"
    _BOLD_FONT = f"{_NORMAL_FONT} bold"
    _H2_FONT = "Calibri 18 bold"

    def __init__(self, description: str):
        # TODO: Add a "header" text box with general instructions (and a goodbye message when the program is done?)

        self._shutdown_requested = False
        self._thread_frame: Dict[str, TaskStatusFrame] = {}

        root_started = Semaphore(0)
        self._gui_thread = Thread(
            name="GUI", target=lambda: self._run_gui(root_started, description)
        )
        self._gui_thread.start()
        # Wait for the GUI to enter the main loop
        root_started.acquire()

    def log(self, task_name: str, level: LogLevel, message: str):
        # TODO: What if the shutdown happens while in the middle of logging something?
        if self._shutdown_requested:
            return

        if not self._should_log(level):
            return

        log_time = datetime.now()

        # TODO: Is it safe to just update the GUI directly? Would it be better to use after()?
        # The tkinter docs seem to imply it is safe: https://docs.python.org/3/library/tkinter.html#threading-model
        if task_name not in self._thread_frame:
            self._thread_frame[task_name] = self._add_row(
                task_name, log_time, level, message
            )
        else:
            frame = self._thread_frame[task_name]
            frame.update_contents(datetime.now(), level, message)

    def input(self, prompt: str, title: str = "") -> Union[str, None]:
        return simpledialog.askstring(title=title, prompt=prompt, show="*")

    def input_password(self, prompt: str, title: str = "") -> Union[str, None]:
        return simpledialog.askstring(title=title, prompt=prompt, show="*")

    def wait(self, task_name: str, prompt: str):
        if self._shutdown_requested:
            return

        frame = ActionItemFrame(
            self._action_items_frame,
            task_name=task_name,
            prompt=prompt,
            font=self._NORMAL_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
            padding=5
        )
        frame.grid(sticky="w")
        self._root_frame.update_scrollregion()
        frame.wait_for_click()
        # Update the scrollregion again in case it got smaller
        self._root_frame.update_scrollregion()

    def close(self):
        # Leave the GUI open until the user closes the window

        # TODO: Skip all this if the window is already closed
        if self._shutdown_requested:
            return

        goodbye_message_textbox = CopyableText(
            self._root_frame,
            width=170,
            font=self._NORMAL_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        goodbye_message_textbox.grid(sticky="W", pady=25)
        goodbye_message_textbox.set_text(
            "All tasks are complete. Close this window to exit."
        )
        self._root_frame.update_scrollregion()

    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def _run_gui(self, root_started: Semaphore, description: str):
        # TODO: Make the GUI responsive

        # Try to make the GUI less blurry
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

        self._tk = Tk()
        self._tk.title("MCR Teardown")
        self._tk.protocol("WM_DELETE_WINDOW", self._confirm_exit)
        self._tk.config(background=self._BACKGROUND_COLOUR)

        self._root_frame = ScrollableFrame(self._tk)

        style = Style()
        # TODO: Change button background?
        style.configure(  # type: ignore
            "TButton",
            font=self._NORMAL_FONT,
        )
        style.configure(  # type: ignore
            "TFrame",
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )

        description_textbox = CopyableText(
            self._root_frame,
            width=170,
            font=self._NORMAL_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        description_textbox.grid(sticky="W", pady=25)
        description_textbox.set_text(description)

        action_items_header = CopyableText(
            self._root_frame,
            font=self._H2_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        action_items_header.grid(sticky="W", pady=25)
        action_items_header.set_text("Action Items")

        self._action_items_frame = Frame(self._root_frame)
        self._action_items_frame.grid(sticky="W")

        action_items_description = CopyableText(
            self._action_items_frame,
            font=self._NORMAL_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        action_items_description.grid(sticky="W", pady=15)
        action_items_description.set_text(
            "Tasks that you must perform manually are listed here."
        )

        thread_statuses_header = CopyableText(
            self._root_frame,
            font=self._H2_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        thread_statuses_header.grid(sticky="W", pady=25)
        thread_statuses_header.set_text("Thread Statuses")

        self._thread_statuses_frame = Frame(self._root_frame)
        self._thread_statuses_frame.grid(sticky="W")

        thread_statuses_description = CopyableText(
            self._thread_statuses_frame,
            font=self._NORMAL_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        thread_statuses_description.grid(sticky="W", pady=15)
        thread_statuses_description.set_text(
            "The status of all in-progress and completed threads are listed here."
        )

        self._tk.after(0, lambda: root_started.release())
        self._tk.mainloop()

    def _close(self):
        # TODO: Release waiting threads?
        self._shutdown_requested = True
        # For some reason, using destroy() instead of quit() causes an error
        self._tk.quit()

    def _confirm_exit(self):
        should_exit = messagebox.askyesno(  # type: ignore
            title="Confirm exit", message="Are you sure you want to exit?"
        )
        if should_exit:
            self._close()

    def _add_row(
        self, task_name: str, log_time: datetime, level: LogLevel, message: str
    ) -> TaskStatusFrame:
        frame = TaskStatusFrame(
            self._thread_statuses_frame,
            task_name,
            datetime.now(),
            level,
            message,
            font=self._NORMAL_FONT,
            padding=5,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        frame.grid(sticky="W")
        self._root_frame.update_scrollregion()
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

    # TODO: Store the task name directly in the Messenger and give each task its own Messenger instance?

    def __init__(self, file_messenger: FileMessenger, input_messenger: InputMessenger):
        self._file_messenger = file_messenger
        self._input_messenger = input_messenger

    def log(self, task_name: str, level: LogLevel, message: str):
        self.log_separate(task_name, level, message, message)

    def log_separate(
        self,
        task_name: str,
        level: LogLevel,
        console_message: str,
        log_file_message: str,
    ):
        self._file_messenger.log(task_name, level, log_file_message)
        self._input_messenger.log(task_name, level, console_message)

    def input(self, prompt: str) -> Union[str, None]:
        return self._input_messenger.input(prompt)

    def input_password(self, prompt: str) -> Union[str, None]:
        return self._input_messenger.input_password(prompt)

    def wait(self, task_name: str, prompt: str):
        self._input_messenger.wait(task_name, prompt)

    def close(self):
        self._input_messenger.close()

    def shutdown_requested(self) -> bool:
        return self._input_messenger.shutdown_requested()


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
