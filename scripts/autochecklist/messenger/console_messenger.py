from __future__ import annotations

import logging
import math
from argparse import ArgumentTypeError
from dataclasses import dataclass, field
from datetime import datetime
from getpass import getpass
from logging import StreamHandler
from queue import Empty, PriorityQueue
from threading import Lock, Thread
from typing import Callable, Dict, Literal, Optional, TypeVar, Union

from autochecklist.messenger.input_messenger import (
    InputMessenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
    interrupt_main_thread,
    is_current_thread_main,
)

T = TypeVar("T")


# TODO: Restore log levels so that user can ignore status updates by default?
class ConsoleMessenger(InputMessenger):
    """
    IMPORTANT: It is NOT safe to call any method other than close after the
    main thread receives a CTRL+C event (which normally appears as a
    `KeyboardInterrupt`). It is possible that the messenger has already
    received the event and is already in the process of shutting down.
    """

    def __init__(self, description: str, log_level: int = logging.INFO):
        print(f"{description}\n\n")

        handler = StreamHandler()
        handler.setLevel(log_level)
        handler.setFormatter(
            logging.Formatter(fmt="[%(levelname)-8s] %(message)s"),
        )
        self._console_logger = logging.getLogger("console_messenger")
        self._console_logger.setLevel(log_level)
        self._console_logger.addHandler(handler)

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

    def input_bool(self, prompt: str, title: str = "") -> bool:
        def read_input() -> bool:
            print(f"{prompt} [Y/N]")
            while True:
                result = input("> ")
                if result.lower() in ["y", "yes"]:
                    return True
                elif result.lower() in ["n", "no"]:
                    return False
                else:
                    print("Invalid input. Enter 'y' for yes or 'n' for no.")

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
            is_from_main_thread=is_current_thread_main(),
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
            is_from_main_thread=is_current_thread_main(),
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
                        is_from_main_thread=is_current_thread_main(),
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
                        interrupt_main_thread()
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
