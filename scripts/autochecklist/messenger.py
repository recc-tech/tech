from __future__ import annotations

import ctypes
import logging
import math
import os
import signal
import threading
from argparse import ArgumentTypeError
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from getpass import getpass
from logging import FileHandler, Handler, StreamHandler
from pathlib import Path
from queue import Empty, PriorityQueue
from threading import Event, Lock, Semaphore, Thread, local
from tkinter import Canvas, Misc, Text, Tk, Toplevel, messagebox
from tkinter.ttk import Button, Entry, Frame, Label, Scrollbar, Style
from typing import Callable, Dict, Literal, Optional, Set, Tuple, TypeVar, Union, cast

T = TypeVar("T")


class Messenger:
    """Thread-safe class for logging and user interactions."""

    ROOT_PSEUDOTASK_NAME = "SCRIPT MAIN"
    """Default display name for the main thread."""

    def __init__(self, file_messenger: FileMessenger, input_messenger: InputMessenger):
        self._file_messenger = file_messenger
        self._input_messenger = input_messenger
        self._task_manager = _TaskManager()
        self.set_current_task_name(self.ROOT_PSEUDOTASK_NAME)

    def set_current_task_name(self, task_name: Optional[str]):
        self._task_manager.set_current_task_name(task_name)

    def set_task_index_table(self, task_index_table: Dict[str, int]):
        self._task_manager.set_task_index_table(task_index_table)

    def log_debug(self, message: str, task_name: str = ""):
        self._file_messenger.log(
            task_name=self._task_manager.get_task_name(task_name),
            level=logging.DEBUG,
            message=message,
        )

    def log_status(
        self,
        status: TaskStatus,
        message: str,
        task_name: str = "",
        file_only: bool = False,
    ):
        (task_name, index) = self._task_manager.get_task_name_and_index(task_name)
        log_message = f"Task status: {status}. {message}"
        self._file_messenger.log(task_name, logging.INFO, log_message)
        if not file_only:
            self._input_messenger.log_status(task_name, index, status, message)

    # TODO: It would be nice to show not only the exception but the exception
    # type. For example, `str(key_error)` may just show `the_key` when
    # `KeyError: 'the_key'` would be clearer. Ideally the solution should be
    # easy to use everywhere without copy-pasting.
    def log_problem(
        self,
        level: ProblemLevel,
        message: str,
        stacktrace: str = "",
        task_name: str = "",
    ):
        task_name = self._task_manager.get_task_name(task_name)
        details = f"\n{stacktrace}" if stacktrace else ""
        self._file_messenger.log(task_name, level.to_log_level(), f"{message}{details}")
        self._input_messenger.log_problem(task_name, level, message)

    def input(
        self,
        display_name: str,
        password: bool = False,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> Optional[T]:
        return self._input_messenger.input(
            display_name, password, parser, prompt, title
        )

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        return self._input_messenger.input_multiple(params, prompt, title)

    def wait(self, prompt: str, task_name: str = ""):
        (task_name, index) = self._task_manager.get_task_name_and_index(task_name)
        self._input_messenger.wait(task_name, index, prompt)

    def close(self, wait: bool):
        """
        If `wait` is `False`, the messenger will stop immediately, (as opposed
        to, for example, finishing IO operations that were started but not yet
        completed or waiting for the user to close the window.
        """
        self._input_messenger.close(wait)


class _TaskManager:
    """
    Keep track of the current task by thread and provide access to relevant
    metadata for tasks.
    """

    class _Local(local):
        current_task_name: Optional[str] = None

    def __init__(self):
        self._local = self._Local()
        # Put the root "task" (e.g., the script startup code) at the top by
        # default
        self._task_index_table = {Messenger.ROOT_PSEUDOTASK_NAME: 0}
        self._lock = Lock()

    def set_current_task_name(self, task_name: Optional[str]):
        with self._lock:
            self._local.current_task_name = task_name

    def set_task_index_table(self, task_index_table: Dict[str, int]):
        with self._lock:
            # Don't mutate the input
            self._task_index_table = dict(task_index_table)
            # Let the client override the default placement of the root "task"
            # if they want to
            if Messenger.ROOT_PSEUDOTASK_NAME not in self._task_index_table:
                self._task_index_table[Messenger.ROOT_PSEUDOTASK_NAME] = 0

    def get_task_name(self, task_name: str) -> str:
        if task_name:
            return task_name
        with self._lock:
            return self._local.current_task_name or "UNKNOWN"

    def get_task_name_and_index(self, task_name: str) -> Tuple[str, Optional[int]]:
        with self._lock:
            task_name = task_name or self._local.current_task_name or ""
            index = (
                self._task_index_table[task_name]
                if task_name and task_name in self._task_index_table
                else None
            )
            return (task_name or "UNKNOWN", index)


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
    parser: Callable[[str], object] = lambda x: x
    password: bool = False
    description: str = ""


class InputCancelledException(Exception):
    pass


class InputMessenger:
    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        raise NotImplementedError()

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        raise NotImplementedError()

    def close(self, wait: bool):
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
    ) -> Dict[str, object]:
        raise NotImplementedError()

    def wait(self, task_name: str, index: Optional[int], prompt: str) -> None:
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


# TODO: Review punctuation in input prompts (esp. in check_credentials and mcr_setup)
# TODO: Restore log levels so that user can ignore status updates by default?
class ConsoleMessenger(InputMessenger):
    """
    IMPORTANT: It is NOT safe to call any method other than close after the
    main thread receives a CTRL+C event (which normally appears as a
    `KeyboardInterrupt`). It is possible that the messenger has already
    received the event and is already in the process of shutting down.
    """

    def __init__(self, description: str):
        print(f"{description}\n\n")
        self._console_logger = _initialize_logger(
            name="console_messenger",
            handler=StreamHandler(),
            level=logging.INFO,
            log_format="[%(levelname)-8s] %(message)s",
            date_format="%H:%M:%S",
        )
        self._worker = _ConsoleMessengerWorker()

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        self._worker.submit_output_job(
            level=_ConsoleIOJob.OUT_STATUS,
            priority=math.inf if index is None else index,
            run=lambda: self._console_logger.log(
                level=logging.INFO,
                msg=f"{task_name} is {status}. {message}",
            ),
        )

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        self._worker.submit_output_job(
            level=_ConsoleIOJob.OUT_ERROR,
            priority=0,
            run=lambda: self._console_logger.log(
                level=level.to_log_level(),
                msg=f"[{task_name}] {message}",
            ),
        )

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
                print(prompt)
            while True:
                try:
                    parsed_value = parser(input_func(f"{display_name}:\n> "))
                    return parsed_value
                except ArgumentTypeError as e:
                    print(f"Invalid input: {e}")
                # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so that
                # the worker class can deal with all the cancellation-related
                # issues
                except (KeyboardInterrupt, EOFError):
                    raise
                except BaseException as e:
                    print(f"An error occurred while taking input: {e}")

        return self._worker.submit_input_job(
            level=_ConsoleIOJob.IN_INPUT, priority=0, read_input=read_input
        )

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        def read_input():
            if prompt:
                print(prompt)
            results: Dict[str, object] = {}
            for name, param in params.items():
                input_func = getpass if param.password else input
                first_attempt = True
                while True:
                    try:
                        message = f"{param.display_name}:"
                        if param.description and first_attempt:
                            message += f"\n({param.description})"
                        message += "\n> "
                        raw_value = input_func(message)
                        results[name] = param.parser(raw_value)
                        break
                    except ArgumentTypeError as e:
                        print(f"Invalid input: {e}")
                    # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
                    # that the worker class can deal with all the
                    # cancellation-related issues
                    except (KeyboardInterrupt, EOFError):
                        raise
                    except BaseException as e:
                        print(f"An error occurred while taking input: {e}")
                    first_attempt = False
            return results

        return self._worker.submit_input_job(
            level=_ConsoleIOJob.IN_INPUT, priority=0, read_input=read_input
        )

    def wait(self, task_name: str, index: Optional[int], prompt: str):
        prompt = prompt.strip()
        prompt = prompt if prompt.endswith(".") else f"{prompt}."
        prompt = f"- [{task_name}] {prompt}"

        def wait_for_input():
            while True:
                try:
                    # Ask for a password so that pressing keys other than ENTER
                    # has no effect
                    getpass(prompt)
                    return
                # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so that
                # the worker class can deal with all the cancellation-related
                # issues
                except (KeyboardInterrupt, EOFError):
                    raise
                except BaseException as e:
                    print(f"An error occurred while taking input: {e}")
                    return

        self._worker.submit_input_job(
            level=_ConsoleIOJob.IN_WAIT,
            priority=math.inf if index is None else index,
            read_input=wait_for_input,
        )

    def close(self, wait: bool):
        self._worker.close(finish_existing_jobs=wait)


# TODO: Can I *prove* that this is thread-safe and handles cancellation properly?
# - Notice that, from the moment close() sets self._is_shut_down = True, no new
#   jobs can be added to the queue.
class _ConsoleMessengerWorker:
    """
    Encapsulates all the tricky multithreading code for the `ConsoleMessenger`.
    """

    def __init__(self):
        # Push jobs to a queue and have a dedicated thread handle them. Jobs
        # are handled in the following order:
        #  1. Display errors and warnings (shown first).
        #  2. Display task status updates.
        #  3. Request user input.
        #  4. Wait for user (shown last).
        #
        # For status updates and waiting for the user, jobs may also be sorted
        # by their priority. Jobs with lower priority are shown first. Finally,
        # if all else is equal, the job that was submitted earliest is done
        # first.
        self._queue: PriorityQueue[_ConsoleIOJob] = PriorityQueue()
        self._is_shut_down = False
        self._finish_existing_jobs = True
        # If the worker thread immediately stops once it receives CTRL+C
        # directly from input() or getpass(), it may end up stopping all the
        # threads before the main thread even receives the re-sent signal. The
        # main thread may then think all tasks finished successfully and try
        # using a log_* method in the messenger.
        self._wait_for_close_lock = Lock()
        self._wait_for_close_lock.acquire()
        # Even though PriorityQueue is thread-safe, use a lock to guard the
        # queue AND self._is_shut_down.
        #
        # Suppose there was no lock and consider the case where the worker gets
        # shut down completely after the calling thread checks
        # self._is_shut_down but before the job is inserted into the queue. If
        # the job is an input task, the calling thread would hang because the
        # worker thread would no longer be processing jobs.
        self._lock = Lock()
        # Even though PriorityQueue is thread-safe, use a semaphore to handle
        # new entries to the queue. This gives the code the chance to use the
        # general lock *before* reading from the queue.
        self._worker_thread = Thread(
            name="ConsoleMessenger", target=self._run_worker_thread, daemon=True
        )
        self._worker_thread.start()

    def submit_output_job(
        self, level: OutputJobLevel, priority: float, run: Callable[[], None]
    ):
        job = _ConsoleIOJob(
            level=level,
            priority=priority,
            timestamp=datetime.now(),
            run=run,
            is_from_main_thread=_is_current_thread_main(),
        )
        with self._lock:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            self._queue.put(job)

    def submit_input_job(
        self, level: InputJobLevel, priority: float, read_input: Callable[[], T]
    ) -> T:
        lock = Lock()
        lock.acquire()
        # Set the value to None to get Pylance to stop complaining that it's
        # unbound. The lock guarantees that the input function will get a
        # chance to run before this function returns.
        input_value: T = None  # type: ignore
        ctrl_c: bool = False

        def input_task():
            nonlocal input_value, lock, ctrl_c
            try:
                while True:
                    try:
                        input_value = read_input()
                        return
                    except (KeyboardInterrupt, EOFError):
                        ctrl_c = True
                        raise
                    except ArgumentTypeError as e:
                        print(f"Invalid input: {e}")
                    except BaseException as e:
                        print(f"An error occurred while taking input: {e}")
            finally:
                lock.release()

        job = _ConsoleIOJob(
            level=level,
            priority=priority,
            timestamp=datetime.now(),
            run=input_task,
            is_from_main_thread=_is_current_thread_main(),
            lock=lock,
        )
        with self._lock:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            self._queue.put(job)

        # Wait for the task to be done
        lock.acquire()
        if job.cancelled or ctrl_c:
            raise KeyboardInterrupt()
        else:
            return input_value

    def close(self, finish_existing_jobs: bool):
        with self._lock:
            # Check whether the lock is already locked just in case the client
            # calls close() multiple times.
            if self._wait_for_close_lock.locked():
                self._wait_for_close_lock.release()
            # If self._is_shut_down is true, either the user already called
            # close() or the program was cancelled and the exception was
            # received by the worker thread via input() or getpass(). In either
            # case, there's nothing more to do.
            if not self._is_shut_down:
                self._finish_existing_jobs = finish_existing_jobs
                self._is_shut_down = True

                # Put a fake job in the queue to wake up the worker thread
                def fake_run():
                    raise RuntimeError(
                        "This task shouldn't have been run! There is an issue with the ConsoleMessenger."
                    )

                self._queue.put(
                    _ConsoleIOJob(
                        level=_ConsoleIOJob.OUT_ERROR,
                        priority=-math.inf,
                        timestamp=datetime.min,
                        run=fake_run,
                        is_from_main_thread=_is_current_thread_main(),
                        is_fake=True,
                    )
                )
        # Don't end the program until the worker thread is done. Funky things
        # could happen if the worker is still trying to write to the console
        # as the program is shutting down.
        self._worker_thread.join()

    def _run_worker_thread(self):
        try:
            while True:
                # IMPORTANT: check for shutdown AFTER getting a job from the
                # queue. Otherwise, the job might actually be the fake one
                # placed in the queue by close() to wake up this loop.
                job = self._queue.get(block=True)
                with self._lock:
                    if self._is_shut_down:
                        # Put the job back in the queue so that it doesn't get
                        # forgotten
                        self._queue.put(job)
                        break

                try:
                    job.run()
                except (KeyboardInterrupt, EOFError):
                    # For some reason, when the worker thread is running
                    # input() or getpass(), pressing CTRL+C results in an
                    # EOFError in this worker thread instead of a
                    # KeyboardInterrupt in the main thread. Manually
                    # re-trigger the CTRL+C for consistency.
                    #
                    # Need to set self._is_shut_down so that no new input tasks
                    # are processed before close() is called.
                    with self._lock:
                        self._finish_existing_jobs = False
                        self._is_shut_down = True
                    # If the offending job was submitted by the main thread,
                    # the main thread should already receive a
                    # KeyboardInterrupt from submit_input_job. The second one
                    # might be delivered while the first one is still being
                    # handled, which results in ugly stack traces.
                    if not job.is_from_main_thread:
                        _interrupt_main_thread()
                    break
                except BaseException:
                    continue
        finally:
            self._wait_for_close_lock.acquire()
            # Clear the queue so that input jobs can be released
            while True:
                try:
                    job = self._queue.get(block=False)
                except Empty:
                    return
                if job.is_fake:
                    continue
                if self._finish_existing_jobs and not job.is_input:
                    try:
                        job.run()
                    except BaseException:
                        pass
                else:
                    # The check for job.lock.locked() shouldn't be necessary, but
                    # it doesn't hurt
                    job.cancelled = True
                    if job.lock is not None and job.lock.locked():
                        job.lock.release()


OutputJobLevel = Literal[0, 1]
InputJobLevel = Literal[2, 3]


@dataclass(order=True)
class _ConsoleIOJob:
    OUT_ERROR = 0
    OUT_STATUS = 1
    IN_INPUT = 2
    IN_WAIT = 3

    level: Union[OutputJobLevel, InputJobLevel]
    priority: float
    timestamp: datetime
    run: Callable[[], object] = field(compare=False)
    is_from_main_thread: bool = field(compare=False)
    lock: Optional[Lock] = field(compare=False, default=None)
    cancelled: bool = field(compare=False, default=False)
    is_fake: bool = field(compare=False, default=False)

    @property
    def is_input(self):
        return self.level in [self.IN_INPUT, self.IN_WAIT]


class TkMessenger(InputMessenger):
    _BACKGROUND_COLOUR = "#EEEEEE"
    _FOREGROUND_COLOUR = "#000000"

    _NORMAL_FONT = "Calibri 12"
    _ITALIC_FONT = f"{_NORMAL_FONT} italic"
    _BOLD_FONT = f"{_NORMAL_FONT} bold"
    _H2_FONT = "Calibri 18 bold"

    def __init__(self, description: str):
        self._mutex = Lock()
        self._close_called = False
        self._is_main_thread_waiting_for_input = False
        self._is_shut_down = False
        self._waiting_locks: Set[Lock] = set()
        root_started = Semaphore(0)
        self._gui_thread = Thread(
            name="TkMessenger", target=lambda: self._run_gui(root_started, description)
        )
        self._gui_thread.start()
        # Wait for the GUI to enter the main loop
        root_started.acquire()

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        with self._mutex:
            if self._is_shut_down:
                # TODO: Isn't there a race condition here? If the user presses
                # CTRL+C at *just* the right moment, the main thread will
                # receive two KeyboardInterrupts
                raise KeyboardInterrupt()
            self._task_statuses_grid.upsert_row(
                index=index, task_name=task_name, status=status, message=message
            )
            self._root_frame.update_scrollregion()

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            self._problems_grid.add_row(task_name, level, message)
            self._root_frame.update_scrollregion()

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "Input",
    ) -> Optional[T]:
        # simpledialog.askstring throws an exception each time :(
        # https://stackoverflow.com/questions/53480400/tkinter-askstring-deleted-before-its-visibility-changed
        param = Parameter(display_name, parser, password, description=prompt)
        results = self.input_multiple({"param": param}, prompt="", title=title)
        return cast(Optional[T], results["param"])

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = "Input"
    ) -> Dict[str, object]:
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            (
                w,
                entry_by_name,
                error_message_by_name,
                submit_btn,
            ) = self._create_input_window(title, prompt, params)
            if _is_current_thread_main():
                self._is_main_thread_waiting_for_input = True
        lock = Lock()
        try:
            cancelled = False
            with self._mutex:
                self._waiting_locks.add(lock)
            lock.acquire()

            def handle_close():
                nonlocal cancelled
                should_exit = messagebox.askyesno(  # type: ignore
                    title="Confirm exit",
                    message="Are you sure you want to close the input dialog? This will interrupt whatever task was expecting input.",
                )
                if not should_exit:
                    return
                cancelled = True
                lock.release()

            def handle_submit():
                nonlocal submit_btn
                submit_btn.configure(state="disabled")
                lock.release()

            w.protocol("WM_DELETE_WINDOW", handle_close)
            submit_btn.bind("<Button-1>", lambda _: handle_submit())

            while True:
                # Wait for the button to be pressed or for the window to be closed
                submit_btn.configure(state="normal")
                # TODO: What if the user presses the button right here? Or what
                # if the user changes the values as the code below is reading it?
                # In practice, I doubt this will ever come up though
                lock.acquire()
                with self._mutex:
                    if self._is_shut_down:
                        raise KeyboardInterrupt()
                if cancelled:
                    raise InputCancelledException("The user closed the input dialog.")
                output: Dict[str, object] = {}
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
            with self._mutex:
                if lock in self._waiting_locks:
                    self._waiting_locks.remove(lock)
                if _is_current_thread_main():
                    self._is_main_thread_waiting_for_input = False
                # If quit() was already called then the entire GUI is already
                # being destroyed. If this call to destroy() happens after the
                # GUI mainloop exits, then this code will deadlock.
                if not self._is_shut_down:
                    w.destroy()

    def wait(self, task_name: str, index: Optional[int], prompt: str):
        def handle_done_click(btn: Button):
            btn.configure(state="disabled")
            lock.release()

        lock = Lock()
        with self._mutex:
            self._waiting_locks.add(lock)
        lock.acquire()
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            actual_index = self._action_items_grid.add_row(
                index,
                task_name=task_name,
                message=prompt,
                onclick=lambda btn: handle_done_click(btn),
            )
            self._root_frame.update_scrollregion()
        lock.acquire()
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            self._waiting_locks.remove(lock)
            self._action_items_grid.delete_row(actual_index)
            # Update the scrollregion again in case it got smaller
            self._root_frame.update_scrollregion()

    def close(self, wait: bool):
        with self._mutex:
            self._close_called = True
            if not self._is_shut_down:
                goodbye_message_textbox = _CopyableText(
                    self._action_items_container,
                    width=170,
                    font=self._NORMAL_FONT,
                    background=self._BACKGROUND_COLOUR,
                    foreground=self._FOREGROUND_COLOUR,
                )
                goodbye_message_textbox.grid(sticky="W", pady=25)
                goodbye_message_textbox.set_text(
                    "The program is done. Close this window to exit."
                )
                self._root_frame.update_scrollregion()
        if not wait:
            self._quit()
        self._gui_thread.join()

    def _run_gui(self, root_started: Semaphore, description: str):
        # TODO: Make the GUI responsive. I would need to find a way of having
        # the Text widgets fill the width of the screen, which doesn't seem to
        # be available out of the box.

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

        self._root_frame = _ScrollableFrame(self._tk)

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

        description_textbox = _CopyableText(
            self._root_frame,
            width=170,
            font=self._ITALIC_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        description_textbox.grid(sticky="NEW", pady=25)
        description_textbox.set_text(description)

        action_items_header = _CopyableText(
            self._root_frame,
            font=self._H2_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        action_items_header.grid(sticky="NEW", pady=(50, 0))
        action_items_header.set_text("Action Items")

        self._action_items_container = Frame(self._root_frame, style="Test.TFrame")
        self._action_items_container.grid(sticky="NEW")

        action_items_description = _CopyableText(
            self._action_items_container,
            font=self._ITALIC_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        action_items_description.grid(sticky="NEW", pady=25)
        action_items_description.set_text(
            "Tasks that you must perform manually are listed here."
        )

        self._action_items_grid = _ActionItemGrid(
            self._action_items_container,
            outer_padding=5,
            padx=5,
            pady=5,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
            normal_font=self._NORMAL_FONT,
            header_font=self._BOLD_FONT,
        )
        self._action_items_grid.grid(sticky="NEW")

        task_statuses_header = _CopyableText(
            self._root_frame,
            font=self._H2_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        task_statuses_header.grid(sticky="NEW", pady=(50, 0))
        task_statuses_header.set_text("Task Statuses")

        task_statuses_container = Frame(self._root_frame)
        task_statuses_container.grid(sticky="NEW")

        task_statuses_description = _CopyableText(
            task_statuses_container,
            font=self._ITALIC_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        task_statuses_description.grid(sticky="NEW", pady=25)
        task_statuses_description.set_text("The status of each task is listed here.")

        self._task_statuses_grid = _TaskStatusGrid(
            task_statuses_container,
            outer_padding=5,
            padx=5,
            pady=5,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
            normal_font=self._NORMAL_FONT,
            header_font=self._BOLD_FONT,
            bold_font=self._BOLD_FONT,
        )
        self._task_statuses_grid.grid(sticky="NEW")

        problems_header = _CopyableText(
            self._root_frame,
            font=self._H2_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        problems_header.grid(sticky="NEW", pady=(50, 0))
        problems_header.set_text("Problems")

        self._problems_container = Frame(self._root_frame)
        self._problems_container.grid(sticky="NEW")

        problems_description = _CopyableText(
            self._problems_container,
            font=self._ITALIC_FONT,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
        )
        problems_description.grid(sticky="NEW", pady=25)
        problems_description.set_text("Potential problems are listed here.")

        self._problems_grid = _ProblemGrid(
            self._problems_container,
            outer_padding=5,
            padx=5,
            pady=5,
            background=self._BACKGROUND_COLOUR,
            foreground=self._FOREGROUND_COLOUR,
            normal_font=self._NORMAL_FONT,
            header_font=self._BOLD_FONT,
            bold_font=self._BOLD_FONT,
        )
        self._problems_grid.grid(sticky="NEW")

        self._tk.after(0, lambda: root_started.release())
        self._tk.mainloop()

    def _create_input_window(
        self, title: str, prompt: str, params: Dict[str, Parameter]
    ) -> Tuple[Toplevel, Dict[str, Entry], Dict[str, _CopyableText], Button]:
        entry_by_name: Dict[str, Entry] = {}
        error_message_by_name: Dict[str, _CopyableText] = {}
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
                    description_box = _CopyableText(
                        w, background=self._BACKGROUND_COLOUR
                    )
                    description_box.grid()
                    description_box.set_text(param.description)
                error_message = _CopyableText(w, background=self._BACKGROUND_COLOUR)
                error_message.config(foreground="red")
                error_message.grid()
                error_message_by_name[name] = error_message
            btn = Button(w, text="Done")
            btn.grid()
        except BaseException:
            w.destroy()
            raise
        return (w, entry_by_name, error_message_by_name, btn)

    def _confirm_exit(self):
        should_exit = messagebox.askyesno(  # type: ignore
            title="Confirm exit", message="Are you sure you want to exit?"
        )
        if should_exit:
            with self._mutex:
                # If the client called close(), it expects the user to close
                # the window, so there's no need to notify it. But if it hasn't
                # called close, it's probably not done yet and needs to be
                # interrupted.
                #
                # If an input dialog is open in the main thread,
                if (
                    not self._close_called
                    and not self._is_main_thread_waiting_for_input
                ):
                    _interrupt_main_thread()
            self._quit()

    def _quit(self):
        with self._mutex:
            # If the GUI thread isn't alive, then probably _quit() was already
            # called
            # TODO: Change this to self._is_shut_down
            if not self._gui_thread.is_alive():
                return
            self._is_shut_down = True
            for lock in self._waiting_locks:
                if lock.locked():
                    lock.release()
            self._tk.quit()


class _ScrollableFrame(Frame):
    def __init__(self, parent: Misc, *args: object, **kwargs: object):
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


class _CopyableText(Text):
    """
    Text widget that supports both text wrapping and copying its contents to the clipboard.
    """

    def __init__(self, parent: Misc, *args: object, **kwargs: object):
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


class _ThickSeparator(Frame):
    def __init__(
        self,
        parent: Misc,
        thickness: int,
        orient: Literal["horizontal", "vertical"],
        colour: str,
    ):
        STYLE = "ThickSeparator.TFrame"
        if orient == "horizontal":
            super().__init__(parent, height=thickness, style=STYLE)
        else:
            super().__init__(parent, width=thickness, style=STYLE)
        Style().configure(STYLE, background=colour)  # type: ignore


class _ActionItemGrid(Frame):
    _BTN_COLUMN = 0
    _BTN_WIDTH = 20
    _NAME_COLUMN = 1
    _NAME_WIDTH = 35
    _MSG_COLUMN = 2
    _MSG_WIDTH = 100

    def __init__(
        self,
        parent: Misc,
        outer_padding: int,
        padx: int,
        pady: int,
        background: str,
        foreground: str,
        normal_font: str,
        header_font: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(parent, padding=outer_padding, *args, **kwargs)

        self._padx = padx
        self._pady = pady
        self._background = background
        self._foreground = foreground
        self._normal_font = normal_font
        self._header_font = header_font

        self._widgets: Dict[int, Tuple[Button, _CopyableText, _CopyableText]] = {}
        self._create_header()

    def add_row(
        self,
        index: Optional[int],
        task_name: str,
        message: str,
        onclick: Callable[[Button], None],
    ) -> int:
        if index is None or index in self._widgets:
            # If the index is the same as an existing row, tkinter seems to
            # overwrite the existing widgets. It's better to avoid that and
            # just put this action item at the buttom.
            actual_index = max(self._widgets.keys()) + 1 if self._widgets else 0
        else:
            actual_index = index

        button = Button(self, text="Done", state="enabled", width=self._BTN_WIDTH)
        button.configure(command=lambda: onclick(button))
        button.grid(
            # Increase the row number to account for the header
            row=actual_index + 2,
            column=self._BTN_COLUMN,
            padx=self._padx,
            pady=self._pady,
        )
        name_label = _CopyableText(
            self,
            width=self._NAME_WIDTH,
            font=self._normal_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_label.grid(
            row=actual_index + 2,
            column=self._NAME_COLUMN,
            padx=self._padx,
            pady=self._pady,
        )
        name_label.set_text(task_name)
        msg_label = _CopyableText(
            self,
            width=self._MSG_WIDTH,
            font=self._normal_font,
            background=self._background,
            foreground=self._foreground,
        )
        msg_label.grid(
            row=actual_index + 2,
            column=self._MSG_COLUMN,
            padx=self._padx,
            pady=self._pady,
        )
        msg_label.set_text(message)

        self._widgets[actual_index] = (button, name_label, msg_label)

        return actual_index

    def delete_row(self, index: int):
        if index not in self._widgets:
            return
        (button, name_label, msg_label) = self._widgets[index]
        button.destroy()
        name_label.destroy()
        msg_label.destroy()

    def _create_header(self):
        # Include the empty header cell just to keep the UI stable whether or
        # not the grid has entries
        button_header_label = _CopyableText(
            self,
            width=self._BTN_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        button_header_label.grid(
            row=0, column=self._BTN_COLUMN, padx=self._padx, pady=self._pady
        )

        name_header_label = _CopyableText(
            self,
            width=self._NAME_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_header_label.grid(
            row=0, column=self._NAME_COLUMN, padx=self._padx, pady=self._pady
        )
        name_header_label.set_text("Task")

        msg_header_label = _CopyableText(
            self,
            width=self._MSG_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        msg_header_label.grid(
            row=0, column=self._MSG_COLUMN, padx=self._padx, pady=self._pady
        )
        msg_header_label.set_text("Instructions")

        separator = _ThickSeparator(
            self, thickness=3, orient="horizontal", colour="black"
        )
        separator.grid(row=1, column=0, columnspan=3, sticky="EW")


class _TaskStatusGrid(Frame):
    _NAME_COLUMN = 1
    _NAME_WIDTH = 35
    _STATUS_COLUMN = 0
    _STATUS_WIDTH = 20
    _MSG_COLUMN = 2
    _MSG_WIDTH = 100

    def __init__(
        self,
        parent: Misc,
        outer_padding: int,
        padx: int,
        pady: int,
        background: str,
        foreground: str,
        normal_font: str,
        header_font: str,
        bold_font: str,
        *args: object,
        **kwargs: object,
    ):
        super().__init__(parent, padding=outer_padding, *args, **kwargs)

        self._outer_padding = outer_padding
        self._padx = padx
        self._pady = pady
        self._background = background
        self._foreground = foreground
        self._normal_font = normal_font
        self._header_font = header_font
        self._bold_font = bold_font

        self._widgets: Dict[int, Tuple[_CopyableText, _CopyableText]] = {}
        self._index_to_name: Dict[int, str] = {}
        self._create_header()

    def upsert_row(
        self, index: Optional[int], task_name: str, status: TaskStatus, message: str
    ):
        is_index_taken = (
            index in self._index_to_name and self._index_to_name[index] != task_name
        )
        if index is None or is_index_taken:
            actual_index = (
                max(self._index_to_name.keys()) + 1 if self._index_to_name else 0
            )
        else:
            actual_index = index

        row_already_exists = actual_index in self._widgets
        if row_already_exists:
            (status_label, msg_label) = self._widgets[actual_index]
        else:
            name_label = _CopyableText(
                self,
                width=self._NAME_WIDTH,
                font=self._normal_font,
                background=self._background,
                foreground=self._foreground,
            )
            name_label.grid(
                # Increase the row number to account for the header
                row=actual_index + 2,
                column=self._NAME_COLUMN,
                padx=self._padx,
                pady=self._pady,
            )
            name_label.set_text(task_name)
            status_label = _CopyableText(
                self,
                width=self._STATUS_WIDTH,
                font=self._bold_font,
                background=self._background,
                foreground=self._foreground,
            )
            status_label.grid(
                row=actual_index + 2,
                column=self._STATUS_COLUMN,
                padx=self._padx,
                pady=self._pady,
            )
            msg_label = _CopyableText(
                self,
                width=self._MSG_WIDTH,
                font=self._normal_font,
                background=self._background,
                foreground=self._foreground,
            )
            msg_label.grid(
                row=actual_index + 2,
                column=self._MSG_COLUMN,
                padx=self._padx,
                pady=self._pady,
            )
            self._widgets[actual_index] = (status_label, msg_label)

        status_label.set_text(str(status))
        status_label.config(foreground=self._status_colour(status))
        msg_label.set_text(message)
        self._index_to_name[actual_index] = task_name

    def _create_header(self):
        name_header_label = _CopyableText(
            self,
            width=self._NAME_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_header_label.grid(
            row=0, column=self._NAME_COLUMN, padx=self._padx, pady=self._pady
        )
        name_header_label.set_text("Task")

        status_header_label = _CopyableText(
            self,
            width=self._STATUS_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        status_header_label.grid(
            row=0, column=self._STATUS_COLUMN, padx=self._padx, pady=self._pady
        )
        status_header_label.set_text("Status")

        msg_header_label = _CopyableText(
            self,
            width=self._MSG_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        msg_header_label.grid(
            row=0, column=self._MSG_COLUMN, padx=self._padx, pady=self._pady
        )
        msg_header_label.set_text("Details")

        separator = _ThickSeparator(
            self, thickness=3, orient="horizontal", colour="black"
        )
        separator.grid(row=1, column=0, columnspan=3, sticky="EW")

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
        else:
            return "#000000"


class _ProblemGrid(Frame):
    _NAME_COLUMN = 1
    _NAME_WIDTH = 35
    _LEVEL_COLUMN = 0
    _LEVEL_WIDTH = 20
    _MSG_COLUMN = 2
    _MSG_WIDTH = 100

    def __init__(
        self,
        parent: Misc,
        outer_padding: int,
        padx: int,
        pady: int,
        background: str,
        foreground: str,
        normal_font: str,
        header_font: str,
        bold_font: str,
        *args: object,
        **kwargs: object,
    ):
        super().__init__(parent, padding=outer_padding, *args, **kwargs)

        self._outer_padding = outer_padding
        self._padx = padx
        self._pady = pady
        self._background = background
        self._foreground = foreground
        self._normal_font = normal_font
        self._header_font = header_font
        self._bold_font = bold_font

        self._current_row = 0
        self._create_header()

    def add_row(self, task_name: str, level: ProblemLevel, message: str):
        name_label = _CopyableText(
            self,
            width=self._NAME_WIDTH,
            font=self._normal_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_label.grid(
            # Increase the row number to account for the header
            row=self._current_row + 2,
            column=self._NAME_COLUMN,
            padx=self._padx,
            pady=self._pady,
        )
        name_label.set_text(task_name)

        level_label = _CopyableText(
            self,
            width=self._LEVEL_WIDTH,
            foreground=self._level_colour(level),
            font=self._bold_font,
            background=self._background,
        )
        level_label.grid(
            row=self._current_row + 2,
            column=self._LEVEL_COLUMN,
            padx=self._padx,
            pady=self._pady,
        )
        level_label.set_text(str(level))

        self._message_label = _CopyableText(
            self,
            width=self._MSG_WIDTH,
            font=self._normal_font,
            background=self._background,
            foreground=self._foreground,
        )
        self._message_label.grid(
            row=self._current_row + 2,
            column=self._MSG_COLUMN,
            padx=self._padx,
            pady=self._pady,
        )
        self._message_label.set_text(message)

        self._current_row += 1

    def _create_header(self):
        name_header_label = _CopyableText(
            self,
            width=self._NAME_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_header_label.grid(
            row=0, column=self._NAME_COLUMN, padx=self._padx, pady=self._pady
        )
        name_header_label.set_text("Task")

        level_header_label = _CopyableText(
            self,
            width=self._LEVEL_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        level_header_label.grid(
            row=0, column=self._LEVEL_COLUMN, padx=self._padx, pady=self._pady
        )
        level_header_label.set_text("Level")

        msg_header_label = _CopyableText(
            self,
            width=self._MSG_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        msg_header_label.grid(
            row=0, column=self._MSG_COLUMN, padx=self._padx, pady=self._pady
        )
        msg_header_label.set_text("Details")

        separator = _ThickSeparator(
            self, thickness=3, orient="horizontal", colour="black"
        )
        separator.grid(row=1, column=0, columnspan=3, sticky="EW")

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


def _is_current_thread_main() -> bool:
    return threading.current_thread() is threading.main_thread()


def _interrupt_main_thread():
    print(f"Interrupting main thread (pid {os.getpid()})")
    os.kill(os.getpid(), signal.CTRL_C_EVENT)
    # It seems like the signal isn't delivered until print() is
    # called! But printing nothing doesn't work.
    print(" ", end="", flush=True)
    # TODO: Should I have this function call taskkill /f as a fallback if
    # close() isn't called within 5 seconds?
