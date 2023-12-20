import math
import typing
from argparse import ArgumentTypeError
from dataclasses import dataclass, field
from getpass import getpass
from queue import Empty, PriorityQueue
from threading import Event, Lock
from typing import Callable, Dict, Optional, Set, TypeVar

from .input_messenger import (
    InputMessenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
    UserResponse,
)

T = TypeVar("T")


class ConsoleMessenger(InputMessenger):
    def __init__(self, description: str, show_task_status: bool) -> None:
        self._description = description
        self._show_task_status = show_task_status
        self._start_event = Event()
        self._end_event = Event()
        self._mutex = Lock()
        self._waiting_events: Set[Event] = set()
        self._queue: PriorityQueue[_QueueTask] = PriorityQueue()

    def run_main_loop(self) -> None:
        try:
            print(f"{self._description}\n\nPress CTRL+C to see the menu.\n\n")
            should_exit = False
            while True:
                try:
                    try:
                        task = self._queue.get(timeout=0.5)
                    except Empty:
                        if should_exit:
                            return
                        else:
                            continue
                    if not task.is_real:
                        should_exit = True
                    elif should_exit and task.is_input:
                        continue
                    else:
                        task.run()
                except (KeyboardInterrupt, EOFError):
                    # TODO: Show list of commands here, quit on second CTRL+C
                    print("\nProgram cancelled.")
                    return
                except Exception as e:
                    print(f"Error while running task from queue: {e}")
        finally:
            # Release all waiting threads so they can exit cleanly
            for e in self._waiting_events:
                e.set()
            self._start_event.set()
            self._end_event.set()

    def wait_for_start(self) -> None:
        self._start_event.set()

    def close(self) -> None:
        """
        Signal to the messenger that it is time to exit. Queued output tasks
        will be completed, but input tasks will be skipped.
        """
        self._queue.put(
            _QueueTask(
                is_real=False,
                # The rest of the arguments are irrelevant
                index=0,
                is_input=False,
                run=lambda: None,
            )
        )

    @property
    def is_closed(self) -> bool:
        return self._end_event.is_set()

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        def do_log_status() -> None:
            print(f"({task_name} | {status}) {message}")

        if self.is_closed:
            raise KeyboardInterrupt()
        if not self._show_task_status:
            return
        self._queue.put(
            _QueueTask(
                is_real=True,
                index=index if index is not None else math.inf,
                is_input=False,
                run=do_log_status,
            )
        )

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        def do_log_problem() -> None:
            print(f"[{task_name} | {level}] {message}")

        if self.is_closed:
            raise KeyboardInterrupt()
        self._queue.put(
            _QueueTask(
                is_real=True,
                index=0,
                is_input=False,
                run=do_log_problem,
            )
        )

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> T:
        params = {
            "param": Parameter(
                display_name=display_name, parser=parser, password=password
            )
        }
        output = self.input_multiple(params, prompt=prompt, title=title)
        return typing.cast(T, output["param"])

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        def read_input() -> None:
            if prompt:
                print(f"\n{prompt}")
            for name, param in params.items():
                input_func = getpass if param.password else input
                first_attempt = True
                while True:
                    try:
                        message = f"{param.display_name}:"
                        if param.default:
                            message += f"\n[default: {param.default}]"
                        if param.description and first_attempt:
                            message += f"\n({param.description})"
                        message += "\n> "
                        raw_value = input_func(message)
                        if not raw_value and param.default:
                            raw_value = param.default
                        output_by_key[name] = param.parser(raw_value)
                        break
                    except ArgumentTypeError as e:
                        print(f"Invalid input: {e}")
                    # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
                    # that the main loop can deal with all the
                    # cancellation-related issues
                    except (KeyboardInterrupt, EOFError):
                        raise
                    except Exception as e:
                        print(f"An error occurred while taking input: {e}")
                    first_attempt = False
            submit_event.set()
            return

        output_by_key: Dict[str, object] = {key: "" for key in params}
        submit_event = Event()
        self._queue.put(
            _QueueTask(
                is_real=True,
                index=0,
                is_input=True,
                run=read_input,
            )
        )
        with self._mutex:
            self._waiting_events.add(submit_event)
        submit_event.wait()
        with self._mutex:
            self._waiting_events.remove(submit_event)
        return output_by_key

    def input_bool(self, prompt: str, title: str = "") -> bool:
        def read_input() -> None:
            nonlocal choice
            print(f"\n{prompt} [y/n]")
            while True:
                try:
                    result = input(">> ")
                    if result.lower() in ["y", "yes"]:
                        choice = True
                        submit_event.set()
                        return
                    elif result.lower() in ["n", "no"]:
                        choice = False
                        submit_event.set()
                        return
                    else:
                        print("Invalid input. Enter 'y' for yes or 'n' for no.")
                # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
                # that the main loop can deal with all the
                # cancellation-related issues
                except (KeyboardInterrupt, EOFError):
                    raise
                except Exception as e:
                    print(f"An error occurred while waiting for input: {e}")
                    continue

        submit_event = Event()
        choice: bool = True
        self._queue.put(
            _QueueTask(
                is_real=True,
                index=0,
                is_input=True,
                run=read_input,
            )
        )
        with self._mutex:
            self._waiting_events.add(submit_event)
        submit_event.wait()
        with self._mutex:
            self._waiting_events.remove(submit_event)
        return choice

    def wait(
        self, task_name: str, index: Optional[int], prompt: str, allow_retry: bool
    ) -> UserResponse:
        def wait_for_input_with_retry() -> None:
            nonlocal response
            print(
                f"{prompt} Type 'retry' if you would like to try completing the task automatically again. Type 'done' if you have completed the task manually.",
            )
            while True:
                try:
                    choice = input(">> ")
                    if choice.lower() == "done":
                        response = UserResponse.DONE
                        input_received_event.set()
                        return
                    elif choice.lower() == "retry":
                        response = UserResponse.RETRY
                        input_received_event.set()
                        return
                    else:
                        print(
                            "Invalid choice. Type 'retry' if you would like to try completing the task automatically again. Type 'done' if you have completed the task manually."
                        )
                        continue
                # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
                # that the main loop can deal with all the
                # cancellation-related issues
                except (KeyboardInterrupt, EOFError):
                    raise
                except Exception as e:
                    print(
                        f"An error occurred while waiting for input. Assuming the task was completed manually. {e}"
                    )
                    response = UserResponse.DONE
                    input_received_event.set()
                    return

        def wait_for_input() -> None:
            nonlocal response
            try:
                # Ask for a password so that pressing keys other than
                # ENTER has no visible effect
                getpass(f"{prompt} Press ENTER when you're done.\n>> ")
                response = UserResponse.DONE
                input_received_event.set()
            # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
            # that the main loop can deal with all the
            # cancellation-related issues
            except (KeyboardInterrupt, EOFError):
                raise
            except Exception as e:
                print(
                    f"An error occurred while waiting for input. Assuming the task was completed manually. {e}"
                )
                response = UserResponse.DONE
                input_received_event.set()

        prompt = prompt.strip()
        prompt = (
            prompt
            if prompt.endswith(".") or prompt.endswith("'.") or prompt.endswith('".')
            else f"{prompt}."
        )
        prompt = f"\n({task_name}) {prompt}"
        response: Optional[UserResponse] = None
        input_received_event = Event()
        self._queue.put(
            _QueueTask(
                is_real=True,
                index=index if index is not None else math.inf,
                is_input=True,
                run=wait_for_input_with_retry if allow_retry else wait_for_input,
            )
        )
        with self._mutex:
            self._waiting_events.add(input_received_event)
        input_received_event.wait()
        if self.is_closed:
            raise KeyboardInterrupt()
        with self._mutex:
            self._waiting_events.remove(input_received_event)
        # Response should always be set by this point, but set default just in
        # case. Default to DONE rather than RETRY so that the script doesn't
        # get stuck in an infinite loop
        return response or UserResponse.DONE

    def _wait_for_event(self, event: Event) -> None:
        with self._mutex:
            self._waiting_events.add(event)
        event.wait()
        with self._mutex:
            self._waiting_events.remove(event)
        if self.is_closed:
            raise KeyboardInterrupt()


@dataclass(frozen=True, order=True)
class _QueueTask:
    is_real: bool
    """Set this to `False` to signal that it's time to exit."""
    is_input: bool
    index: float
    run: Callable[[], None] = field(compare=False)
