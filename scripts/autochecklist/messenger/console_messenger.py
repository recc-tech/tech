from __future__ import annotations

import math
import threading
import time
import typing
from argparse import ArgumentTypeError
from dataclasses import dataclass, field
from getpass import getpass
from queue import Empty, PriorityQueue
from threading import Event, Lock
from typing import Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar

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
        self._commands: Dict[Tuple[str, str], Callable[[], None]] = {}
        self._waiting_events: Set[Event] = set()
        self._queue: PriorityQueue[_QueueTask] = PriorityQueue()
        self._io = _IO()

    def run_main_loop(self) -> None:
        try:
            startup_message = self._description.strip()
            if startup_message:
                startup_message += "\n\n"
            startup_message += "Press CTRL+C to see the menu.\n" 
            self._io.write(startup_message)
            should_exit = False
            task: Optional[_QueueTask] = None
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
                    # HACK: give time for asynchronous processes to settle down
                    # or something. Without this, a KeyboardInterrupt from
                    # task.run() occasionally just kills the entire program
                    # (particularly when you come out of the menu and then
                    # immediately go into a call to wait() where the user hits
                    # CTRL+C).
                    # https://stackoverflow.com/a/31131378
                    time.sleep(0.25)
                    try:
                        if task is not None:
                            # Re-run it after leaving the menu
                            self._queue.put(task)
                        self._run_menu()
                    except (KeyboardInterrupt, EOFError):
                        self._io.write("\nProgram cancelled.")
                        return
                except Exception as e:
                    self._io.write(f"Error while running task from queue: {e}")
        finally:
            # Release all waiting threads so they can exit cleanly
            for e in self._waiting_events:
                e.set()
            self._start_event.set()
            self._end_event.set()

    def _run_menu(self) -> None:
        command_by_key = self._get_and_display_menu()
        while True:
            choice = self._io.read(">> ")
            if choice == "q":
                raise KeyboardInterrupt()
            elif choice == "p":
                self._io.write()
                return
            elif choice == "r":
                command_by_key = self._get_and_display_menu()
            elif choice in command_by_key:
                try:
                    with self._mutex:
                        task, command = command_by_key[choice]
                        callback = self._commands[task, command]
                except KeyError:
                    self._io.write("That command is no longer available.")
                    continue
                try:
                    callback()
                except Exception as e:
                    self._io.write(f"An error occurred: {e}")
                command_by_key = self._get_and_display_menu()
            elif choice.strip() == "":
                continue
            else:
                self._io.write(f"Unknown choice '{choice}'.")

    def _get_and_display_menu(self) -> Dict[str, Tuple[str, str]]:
        with self._mutex:
            task_command_pairs = sorted(self._commands.keys())
        command_by_key: Dict[str, Tuple[str, str]] = {}
        count = 1
        self._io.write()
        if len(task_command_pairs) == 0:
            self._io.write("\nNo commands available.")
        else:
            for task, command in task_command_pairs:
                command_by_key[str(count)] = (task, command)
                count += 1
            task_header = "TASK"
            command_header = "COMMAND"
            key_header = "KEY"
            max_task_len = max(len(task) for (task, _) in task_command_pairs)
            max_task_len = max(len(task_header), max_task_len)
            max_command_len = max(len(command) for (_, command) in task_command_pairs)
            max_command_len = max(len(command_header), max_command_len)
            self._io.write(
                f"{task_header:<{max_task_len}} | {command_header:<{max_command_len}} | {key_header}"
            )
            for key, (task, command) in command_by_key.items():
                self._io.write(
                    f"{task:<{max_task_len}} | {command:<{max_command_len}} | {key}"
                )
        self._io.write()
        instruction_lines = ["Options:"]
        if len(task_command_pairs) > 0:
            instruction_lines.append("- Enter the key for a command listed above.")
        instruction_lines += [
            "- r: refresh menu",
            "- p: go back to script",
            "- q: quit script",
        ]
        self._io.write("\n".join(instruction_lines))
        return command_by_key

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
            self._io.write(f"({task_name} | {status}) {message}")

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
            self._io.write(f"[{task_name} | {level}] {message}")

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
                self._io.write(f"\n{prompt}")
            for name, param in params.items():
                input_func = self._io.read_password if param.password else self._io.read
                first_attempt = True
                while True:
                    try:
                        default_message = (
                            f" [default: {param.default}]" if param.default else ""
                        )
                        message = f"{param.display_name}{default_message}:"
                        if param.description and first_attempt:
                            message += f"\n({param.description})"
                        self._io.write(message)
                        raw_value = input_func(">> ")
                        if not raw_value and param.default:
                            raw_value = param.default
                        output_by_key[name] = param.parser(raw_value)
                        break
                    except ArgumentTypeError as e:
                        self._io.write(f"Invalid input: {e}")
                    # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
                    # that the main loop can deal with all the
                    # cancellation-related issues
                    except (KeyboardInterrupt, EOFError):
                        raise
                    except Exception as e:
                        self._io.write(f"An error occurred while taking input: {e}")
                    first_attempt = False
            self._io.write()
            submit_event.set()

        output_by_key: Dict[str, object] = {key: "" for key in params}
        submit_event = Event()
        if _is_current_thread_main():
            read_input()
        else:
            self._enqueue_and_wait(
                _QueueTask(
                    is_real=True,
                    index=0,
                    is_input=True,
                    run=read_input,
                ),
                submit_event,
            )
        return output_by_key

    def input_bool(self, prompt: str, title: str = "") -> bool:
        def read_input() -> None:
            nonlocal choice
            self._io.write(f"\n{prompt} [y/n]")
            while True:
                try:
                    result = self._io.read(">> ")
                    if result.lower() in ["y", "yes"]:
                        choice = True
                        self._io.write()
                        submit_event.set()
                        return
                    elif result.lower() in ["n", "no"]:
                        choice = False
                        self._io.write()
                        submit_event.set()
                        return
                    else:
                        self._io.write(
                            "Invalid input. Enter 'y' for yes or 'n' for no."
                        )
                # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
                # that the main loop can deal with all the
                # cancellation-related issues
                except (KeyboardInterrupt, EOFError):
                    raise
                except Exception as e:
                    self._io.write(f"An error occurred while waiting for input: {e}")
                    continue

        submit_event = Event()
        choice: bool = True
        if _is_current_thread_main():
            read_input()
        else:
            self._enqueue_and_wait(
                _QueueTask(
                    is_real=True,
                    index=0,
                    is_input=True,
                    run=read_input,
                ),
                submit_event,
            )
        return choice

    def wait(
        self, task_name: str, index: Optional[int], prompt: str, allow_retry: bool
    ) -> UserResponse:
        def wait_for_input_with_retry() -> None:
            nonlocal response
            self._io.write(
                f"{prompt} Type 'retry' if you would like to try completing the task automatically again. Type 'done' if you have completed the task manually.",
            )
            while True:
                try:
                    choice = self._io.read(">> ")
                    if choice.lower() == "done":
                        response = UserResponse.DONE
                        self._io.write()
                        input_received_event.set()
                        return
                    elif choice.lower() == "retry":
                        response = UserResponse.RETRY
                        self._io.write()
                        input_received_event.set()
                        return
                    else:
                        self._io.write(
                            "Invalid choice. Type 'retry' if you would like to try completing the task automatically again. Type 'done' if you have completed the task manually."
                        )
                        continue
                # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
                # that the main loop can deal with all the
                # cancellation-related issues
                except (KeyboardInterrupt, EOFError):
                    raise
                except Exception as e:
                    self._io.write(
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
                self._io.read_password(f"{prompt} Press ENTER when you're done.\n>> ")
                response = UserResponse.DONE
                self._io.write()
                input_received_event.set()
            # IMPORTANT: Ignore both KeyboardInterrupt and EOFError so
            # that the main loop can deal with all the
            # cancellation-related issues
            except (KeyboardInterrupt, EOFError):
                raise
            except Exception as e:
                self._io.write(
                    f"An error occurred while waiting for input. Assuming the task was completed manually. {e}\n"
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
        run = wait_for_input_with_retry if allow_retry else wait_for_input
        if _is_current_thread_main():
            run()
        else:
            self._enqueue_and_wait(
                _QueueTask(
                    is_real=True,
                    index=index if index is not None else math.inf,
                    is_input=True,
                    run=run,
                ),
                input_received_event,
            )
        # Response should always be set by this point, but set default just in
        # case. Default to DONE rather than RETRY so that the script doesn't
        # get stuck in an infinite loop
        return response or UserResponse.DONE

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        with self._mutex:
            self._commands[task_name, command_name] = callback

    def remove_command(self, task_name: str, command_name: str) -> None:
        with self._mutex:
            try:
                del self._commands[task_name, command_name]
            except KeyError:
                pass

    def _enqueue_and_wait(self, task: _QueueTask, event: Event) -> None:
        self._queue.put(task)
        with self._mutex:
            self._waiting_events.add(event)
        event.wait()
        with self._mutex:
            self._waiting_events.remove(event)
        if self.is_closed:
            raise KeyboardInterrupt()


class _IO:
    """
    Handles printing to the console in such a way that the number of blank
    lines between lines of text is consistent regardless of situation.
    """

    def __init__(self) -> None:
        self._mutex = Lock()
        self._current_blank_lines = 0

    def write(self, text: str = "") -> None:
        if text.strip() == "":
            with self._mutex:
                print()
                self._current_blank_lines += 1
        else:
            lines = text.split("\n")
            num_leading = self._count_leading_blanks(lines)
            num_trailing = self._count_leading_blanks(reversed(lines))
            with self._mutex:
                k = max(0, num_leading - self._current_blank_lines)
                text_to_print = k * "\n" + text.lstrip()
                print(text_to_print)
                self._current_blank_lines = num_trailing

    def read(self, prompt: str = "") -> str:
        return self._read(prompt, input)

    def read_password(self, prompt: str = "") -> str:
        return self._read(prompt, getpass)

    def _read(self, prompt: str, input_func: Callable[[str], str]) -> str:
        if prompt.strip() == "":
            with self._mutex:
                val = input_func(prompt)
                # The user needs to press ENTER to submit, which adds a newline
                self._current_blank_lines += 1
                return val
        else:
            lines = prompt.split("\n")
            num_leading = self._count_leading_blanks(lines)
            # Subtract one because no trailing newline is added
            num_trailing = self._count_leading_blanks(reversed(lines)) - 1
            with self._mutex:
                k = max(0, num_leading - self._current_blank_lines)
                text_to_print = k * "\n" + prompt.lstrip()
                self._current_blank_lines = num_trailing
                val = input_func(text_to_print)
                # The user needs to press ENTER to submit, which adds a newline
                self._current_blank_lines += 1
                return val

    def _count_leading_blanks(self, lines: Iterable[str]) -> int:
        num_leading = 0
        for l in lines:
            if not l.strip():
                num_leading += 1
            else:
                break
        return num_leading


@dataclass(frozen=True, order=True)
class _QueueTask:
    is_real: bool
    """Set this to `False` to signal that it's time to exit."""
    is_input: bool
    index: float
    run: Callable[[], None] = field(compare=False)


def _is_current_thread_main() -> bool:
    return threading.current_thread() is threading.main_thread()
