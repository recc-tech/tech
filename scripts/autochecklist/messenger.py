from __future__ import annotations

import ctypes
import logging
from argparse import ArgumentTypeError
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from getpass import getpass
from logging import FileHandler, Handler, StreamHandler
from pathlib import Path
from threading import Event, Lock, Semaphore, Thread, local
from tkinter import Canvas, Misc, Text, Tk, Toplevel, messagebox
from tkinter.ttk import Button, Entry, Frame, Label, Scrollbar, Style
from typing import Any, Callable, Deque, Dict, TypeVar, Union

T = TypeVar("T")

thread_local = local()
thread_local.current_task_name = None


def current_task_name() -> str:
    return (
        thread_local.current_task_name if thread_local.current_task_name else "UNKNOWN"
    )


def set_current_task_name(name: Union[str, None]):
    thread_local.current_task_name = name


class TaskStatus(Enum):
    NOT_STARTED = auto()
    """
    The task has not yet started.
    """
    RUNNING = auto()
    """
    The automatic implementation of the task is running.
    """
    WAITING_FOR_USER = auto()
    """
    Waiting for user input.
    """
    DONE = auto()
    """
    Task completed, either manually or automatically.
    """

    def __str__(self):
        return self.name


# TODO: Review the use of the different problem levels
class ProblemLevel(Enum):
    WARN = auto()
    """
    Something that may or may not be a problem and does not stop a task from continuing.
    """
    ERROR = auto()
    """
    A problem that prevents the current task from completing successfully.
    """
    FATAL = auto()
    """
    A problem from which the program cannot recover.
    """

    def to_log_level(self) -> int:
        if self == ProblemLevel.WARN:
            return logging.WARN
        elif self == ProblemLevel.ERROR:
            return logging.ERROR
        elif self == ProblemLevel.FATAL:
            return logging.FATAL
        else:
            # This should never happen, but just in case
            return logging.ERROR

    def __str__(self):
        return self.name


@dataclass
class Parameter:
    display_name: str
    parser: Callable[[str], Any] = lambda x: x
    password: bool = False
    description: str = ""


class InputCancelledException(Exception):
    pass


class InputMessenger:
    def log_status(self, task_name: str, status: TaskStatus, message: str) -> None:
        raise NotImplementedError()

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        raise NotImplementedError()

    def close(self):
        """
        Performs any cleanup that is required before exiting (e.g., making worker threads exit).
        """
        pass

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> T:
        raise NotImplementedError()

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, Any]:
        raise NotImplementedError()

    def wait(self, task_name: str, prompt: str) -> None:
        raise NotImplementedError()

    @property
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

    def log(self, task_name: str, level: int, message: str):
        self.file_logger.log(level=level, msg=f"[{task_name:<35}] {message}")


class ConsoleMessenger(InputMessenger):
    @dataclass
    class _LogTask:
        run: Callable[[], Any]
        is_input: bool

    def __init__(self, description: str):
        print(f"{description}\n\n")

        self._should_exit = False
        self._shutdown_requested = False

        self._console_logger = _initialize_logger(
            name="console_messenger",
            handler=StreamHandler(),
            level=logging.INFO,
            log_format="[%(levelname)-8s] %(message)s",
            date_format="%H:%M:%S",
        )

        # Push tasks to a queue and have a dedicated thread handle those operations
        self._task_queue: Deque[ConsoleMessenger._LogTask] = deque()
        self._task_queue_cleared_lock = Lock()
        self._task_queue_cleared_lock.acquire()
        self._task_semaphore = Semaphore(0)
        self._start_thread(name="ConsoleMessenger")

    def log_status(self, task_name: str, status: TaskStatus, message: str) -> None:
        if self._should_exit or self._shutdown_requested:
            return

        self._task_queue.append(
            ConsoleMessenger._LogTask(
                run=lambda: self._console_logger.log(
                    level=logging.INFO,
                    msg=f"{task_name} is {status}. {message}",
                ),
                is_input=False,
            )
        )
        # Signal that there is a task in the queue
        self._task_semaphore.release()

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        if self._should_exit or self._shutdown_requested:
            return

        self._task_queue.append(
            ConsoleMessenger._LogTask(
                run=lambda: self._console_logger.log(
                    level=level.to_log_level(),
                    msg=f"[{task_name}] {message}",
                ),
                is_input=False,
            )
        )
        # Signal that there is a task in the queue
        self._task_semaphore.release()

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> T:
        input_func = getpass if password else input

        def read_input():
            if prompt:
                print()
                print(prompt)
            while True:
                try:
                    parsed_value = parser(input_func(f"{display_name}:\n> "))
                    print()
                    return parsed_value
                except ArgumentTypeError as e:
                    print(f"Invalid input: {e}")
                    print()
                except Exception as e:
                    if isinstance(e, EOFError):
                        raise
                    print(f"An error occurred while taking input: {e}")
                    print()

        return self._input(read_input)

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, Any]:
        def read_input():
            if prompt:
                print()
                print(prompt)
            results: Dict[str, Any] = {}
            for name, param in params.items():
                print()
                input_func = getpass if param.password else input
                first_attempt = True
                while True:
                    try:
                        message = f"Enter the {param.display_name}."
                        if param.description and first_attempt:
                            message += f"\n{param.description}"
                        message += "\n> "
                        raw_value = input_func(message)
                        results[name] = param.parser(raw_value)
                        break
                    except ArgumentTypeError as e:
                        print(f"Invalid input: {e}")
                        print()
                    except Exception as e:
                        if isinstance(e, EOFError):
                            raise
                        print(f"An error occurred while taking input: {e}")
                        print()
                    first_attempt = False
            print()
            return results

        return self._input(read_input)

    def wait(self, task_name: str, prompt: str):
        prompt = prompt.strip()
        prompt = prompt if prompt.endswith(".") else f"{prompt}."
        prompt = f"- [{task_name}] {prompt}"
        # Ask for a password so that pressing keys other than ENTER has no effect
        self.input(f"{prompt} When you are done, press ENTER.", password=True)

    def close(self):
        self._should_exit = True
        # Pretend there's one more entry in the queue to get the threads to exit
        self._task_semaphore.release()
        # Wait for the queue to be cleared
        self._task_queue_cleared_lock.acquire()

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def _start_thread(
        self,
        name: str,
    ):
        def clear_queue():
            while self._task_queue:
                task = self._task_queue.popleft()
                if not task.is_input:
                    task.run()

        def console_tasks_thread():
            try:
                while True:
                    # Wait for there to be a task in the queue
                    self._task_semaphore.acquire()

                    if self._should_exit or self._shutdown_requested:
                        clear_queue()
                        return

                    task = self._task_queue.popleft()
                    # CTRL+C causes an EOFError if the program was waiting for input
                    # The KeyboardInterrupt should also be raised in the main thread, so no need to display anything here
                    try:
                        task.run()
                    except (EOFError, KeyboardInterrupt):
                        self._shutdown_requested = True
                        clear_queue()
                        return
            finally:
                self._task_queue_cleared_lock.release()

        Thread(target=console_tasks_thread, name=name, daemon=True).start()

    def _input(self, read_input: Callable[[], T]) -> T:
        # read_input is the function to be called once this thread has control of the console. It should catch exceptions.

        if self._should_exit or self._shutdown_requested:
            raise RuntimeError("Cannot take input: the user cancelled the program.")

        # Use a lock so that this function blocks until the input is provided
        lock = Lock()
        lock.acquire()

        # Set the value to None to get Pylance to stop complaining that it's unbound.
        # The lock guarantees that the input function will get a chance to run before this function returns.
        input_value: T = None  # type: ignore
        exc: Union[BaseException, None] = None

        def input_task():
            nonlocal input_value, lock, exc
            try:
                input_value = read_input()
            except (EOFError, KeyboardInterrupt) as e:
                exc = e
            finally:
                lock.release()

        self._task_queue.append(
            ConsoleMessenger._LogTask(run=input_task, is_input=True)
        )
        # Signal that there is a task in the queue
        self._task_semaphore.release()
        # Wait for the task to be done
        lock.acquire()

        if isinstance(exc, BaseException):
            # Why does Pylance think this has type Never? D:<
            raise exc  # type: ignore

        return input_value


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
        """
        Updates the text displayed in this widget.

        IMPORTANT: you MUST call a geometry management function for this widget (e.g., pack() or grid()) BEFORE calling this method.
        """
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


class TaskStatusFrame(Frame):
    _PADX = 5

    def __init__(
        self,
        parent: Misc,
        task_name: str,
        status: TaskStatus,
        message: str,
        font: str,
        padding: int,
        background: str,
        foreground: str,
    ):
        super().__init__(parent, padding=padding)

        self._name_label = CopyableText(
            self, width=35, font=font, background=background, foreground=foreground
        )
        self._name_label.grid(row=0, column=0, padx=self._PADX)
        self._name_label.set_text(task_name)

        self._status_label = CopyableText(
            self, width=20, font=font, background=background, foreground=foreground
        )
        self._status_label.grid(row=0, column=1, padx=self._PADX)

        self._message_label = CopyableText(
            self, width=100, font=font, background=background, foreground=foreground
        )
        self._message_label.grid(row=0, column=2, padx=self._PADX)

        self.update_contents(status, message)

    def update_contents(self, status: TaskStatus, message: str):
        self._status_label.set_text(str(status))
        self._status_label.config(foreground=TaskStatusFrame._status_colour(status))
        self._message_label.set_text(message)

    @staticmethod
    def _status_colour(status: TaskStatus) -> str:
        if status == TaskStatus.NOT_STARTED:
            return "#888888"
        elif status == TaskStatus.RUNNING:
            return "#0000FF"
        elif status == TaskStatus.WAITING_FOR_USER:
            return "#FF7700"
        elif status == TaskStatus.DONE:
            return "#009020"


class ProblemFrame(Frame):
    _PADX = 5

    def __init__(
        self,
        parent: Misc,
        task_name: str,
        level: ProblemLevel,
        message: str,
        font: str,
        padding: int,
        background: str,
        foreground: str,
    ):
        super().__init__(parent, padding=padding)

        self._name_label = CopyableText(
            self, width=35, font=font, background=background, foreground=foreground
        )
        self._name_label.grid(row=0, column=0, padx=self._PADX)
        self._name_label.set_text(task_name)

        self._level_label = CopyableText(
            self,
            width=20,
            font=font,
            background=background,
            foreground=ProblemFrame._level_colour(level),
        )
        self._level_label.grid(row=0, column=1, padx=self._PADX)
        self._level_label.set_text(str(level))

        self._message_label = CopyableText(
            self, width=100, font=font, background=background, foreground=foreground
        )
        self._message_label.grid(row=0, column=2, padx=self._PADX)
        self._message_label.set_text(message)

    @staticmethod
    def _level_colour(level: ProblemLevel) -> str:
        if level == ProblemLevel.WARN:
            return "#FF7700"
        elif level == ProblemLevel.ERROR:
            return "#FF0000"
        elif level == ProblemLevel.FATAL:
            return "#990000"
        else:
            return "#000000"


class TkMessenger(InputMessenger):
    _BACKGROUND_COLOUR = "#EEEEEE"
    _FOREGROUND_COLOUR = "#000000"

    _NORMAL_FONT = "Calibri 12"
    _ITALIC_FONT = f"{_NORMAL_FONT} italic"
    _BOLD_FONT = f"{_NORMAL_FONT} bold"
    _H2_FONT = "Calibri 18 bold"

    def __init__(self, description: str):
        self._shutdown_requested = False
        self._task_status_row: Dict[str, TaskStatusFrame] = {}

        root_started = Semaphore(0)
        self._gui_thread = Thread(
            name="GUI", target=lambda: self._run_gui(root_started, description)
        )
        self._gui_thread.start()
        # Wait for the GUI to enter the main loop
        root_started.acquire()

    def log_status(self, task_name: str, status: TaskStatus, message: str) -> None:
        # TODO: What if the shutdown happens while in the middle of logging something?
        if self._shutdown_requested:
            raise KeyboardInterrupt()

        if task_name in self._task_status_row:
            self._task_status_row[task_name].update_contents(status, message)
        else:
            frame = TaskStatusFrame(
                self._task_statuses_container,
                task_name=task_name,
                status=status,
                message=message,
                font=self._NORMAL_FONT,
                background=self._BACKGROUND_COLOUR,
                foreground=self._FOREGROUND_COLOUR,
                padding=5,
            )
            frame.grid(sticky="W")
            self._root_frame.update_scrollregion()
            self._task_status_row[task_name] = frame

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        if self._shutdown_requested:
            raise KeyboardInterrupt()

        frame = ProblemFrame(
            self._problems_container,
            task_name=task_name,
            level=level,
            message=message,
            font=self._NORMAL_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
            padding=5,
        )
        frame.grid(sticky="W")
        self._root_frame.update_scrollregion()

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], Any] = lambda x: x,
        prompt: str = "",
        title: str = "Input",
    ) -> Union[str, None]:
        # simpledialog.askstring throws an exception each time :(
        # https://stackoverflow.com/questions/53480400/tkinter-askstring-deleted-before-its-visibility-changed
        param = Parameter(display_name, parser, password, description=prompt)
        results = self.input_multiple({"param": param}, prompt="", title=title)
        return results["param"]

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = "Input"
    ) -> Dict[str, Any]:
        if self._shutdown_requested:
            raise KeyboardInterrupt()

        # TODO: If the main window is closed while the main thread is waiting for input, the script will not stop properly

        entry_by_name: Dict[str, Entry] = {}
        error_message_by_name: Dict[str, CopyableText] = {}

        w = Toplevel(self._tk, padx=10, pady=10, background=self._BACKGROUND_COLOUR)
        try:
            w.title(title)
            if prompt:
                prompt_box = Label(w, text=prompt)
                prompt_box.grid()
            for name, param in params.items():
                entry_row = Frame(w)
                entry_row.grid()
                name_label = Label(entry_row, text=param.display_name)
                name_label.grid(row=0, column=0)
                if param.password:
                    entry = Entry(entry_row, show="*")
                else:
                    entry = Entry(entry_row)
                entry.grid(row=0, column=1)
                entry_by_name[name] = entry
                if param.description:
                    description_box = CopyableText(
                        w, background=self._BACKGROUND_COLOUR
                    )
                    description_box.grid()
                    description_box.set_text(param.description)
                error_message = CopyableText(w, background=self._BACKGROUND_COLOUR)
                error_message.config(foreground="red")
                error_message.grid()
                error_message_by_name[name] = error_message
            btn = Button(w, text="Done")
            btn.grid()

            cancelled = False
            lock = Lock()
            lock.acquire()

            def handle_close():
                should_exit = messagebox.askyesno(  # type: ignore
                    title="Confirm exit",
                    message="Are you sure you want to close the input dialog? This will interrupt whatever task was expecting input.",
                )
                if not should_exit:
                    return
                nonlocal cancelled
                cancelled = True
                lock.release()

            def handle_submit():
                lock.release()

            w.protocol("WM_DELETE_WINDOW", handle_close)
            btn.bind("<Button-1>", lambda _: handle_submit())

            while True:
                # Wait for the button to be pressed or for the window to be closed
                lock.acquire()
                if cancelled:
                    raise InputCancelledException("The user closed the input dialog.")
                output: Dict[str, Any] = {}
                error = False
                for name, entry in entry_by_name.items():
                    parser = params[name].parser
                    try:
                        val = parser(entry.get())
                        error_message_by_name[name].set_text("")
                        output[name] = val
                    except ArgumentTypeError as e:
                        error_message_by_name[name].set_text(f"Invalid input: {e}")
                        error = True
                    except Exception as e:
                        error_message_by_name[name].set_text(f"An error occurred: {e}")
                        error = True
                if not error:
                    return output
        finally:
            w.destroy()

    def wait(self, task_name: str, prompt: str):
        if self._shutdown_requested:
            raise KeyboardInterrupt()

        frame = ActionItemFrame(
            self._action_items_container,
            task_name=task_name,
            prompt=prompt,
            font=self._NORMAL_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
            padding=5,
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
            self._action_items_container,
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

    @property
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

        screen_height = self._tk.winfo_screenheight()
        approx_screen_width = 16 * screen_height / 9
        window_width = int(approx_screen_width * 0.75)
        window_height = (screen_height * 3) // 4
        self._tk.geometry(f"{window_width}x{window_height}")

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
            font=self._ITALIC_FONT,
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
        action_items_header.grid(sticky="W", pady=(50, 0))
        action_items_header.set_text("Action Items")

        self._action_items_container = Frame(self._root_frame)
        self._action_items_container.grid(sticky="W")

        action_items_description = CopyableText(
            self._action_items_container,
            font=self._ITALIC_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        action_items_description.grid(sticky="W", pady=25)
        action_items_description.set_text(
            "Tasks that you must perform manually are listed here."
        )

        task_statuses_header = CopyableText(
            self._root_frame,
            font=self._H2_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        task_statuses_header.grid(sticky="W", pady=(50, 0))
        task_statuses_header.set_text("Task Statuses")

        self._task_statuses_container = Frame(self._root_frame)
        self._task_statuses_container.grid(sticky="W")

        task_statuses_description = CopyableText(
            self._task_statuses_container,
            font=self._ITALIC_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        task_statuses_description.grid(sticky="W", pady=25)
        task_statuses_description.set_text("The status of each task is listed here.")

        problems_header = CopyableText(
            self._root_frame,
            font=self._H2_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        problems_header.grid(sticky="W", pady=(50, 0))
        problems_header.set_text("Problems")

        self._problems_container = Frame(self._root_frame)
        self._problems_container.grid(sticky="W")

        problems_description = CopyableText(
            self._problems_container,
            font=self._ITALIC_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        problems_description.grid(sticky="W", pady=25)
        problems_description.set_text("Potential problems are listed here.")

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


class Messenger:
    """
    Thread-safe interface for logging to a file and to the console. Also allows for getting user input without having log messages appear in the console and without making logging blocking.
    """

    def __init__(self, file_messenger: FileMessenger, input_messenger: InputMessenger):
        self._file_messenger = file_messenger
        self._input_messenger = input_messenger

    def log_debug(self, message: str, task_name: str = ""):
        if not task_name:
            task_name = current_task_name()
        self._file_messenger.log(task_name, logging.DEBUG, message)

    def log_status(
        self,
        status: TaskStatus,
        message: str,
        task_name: str = "",
        file_only: bool = False,
    ):
        if not task_name:
            task_name = current_task_name()

        log_message = f"Task status: {status}. {message}"
        self._file_messenger.log(task_name, logging.INFO, log_message)

        if not file_only:
            self._input_messenger.log_status(task_name, status, message)

    def log_problem(
        self,
        level: ProblemLevel,
        message: str,
        stacktrace: str = "",
        task_name: str = "",
    ):
        if not task_name:
            task_name = current_task_name()

        details = f"\n{stacktrace}" if stacktrace else ""
        self._file_messenger.log(task_name, level.to_log_level(), f"{message}{details}")

        self._input_messenger.log_problem(task_name, level, message)

    def input(
        self,
        display_name: str,
        password: bool = False,
        parser: Callable[[str], Any] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> Union[str, None]:
        return self._input_messenger.input(
            display_name, password, parser, prompt, title
        )

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, Any]:
        return self._input_messenger.input_multiple(params, prompt, title)

    def wait(self, prompt: str, task_name: str = ""):
        if not task_name:
            task_name = current_task_name()
        self._input_messenger.wait(task_name, prompt)

    def close(self):
        self._input_messenger.close()

    @property
    def shutdown_requested(self) -> bool:
        return self._input_messenger.shutdown_requested


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
