# pyright: reportPrivateUsage=false

from __future__ import annotations

from argparse import ArgumentTypeError
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Dict, Optional, Tuple, TypeVar, cast

import eel

from . import eel_interface as eeli
from .input_messenger import (
    InputMessenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
    UserResponse,
    interrupt_main_thread,
    is_current_thread_main,
)

T = TypeVar("T")


# region: Callbacks to be used by the JavaScript frontend


@eel.expose
def handle_input(values: Dict[str, str]) -> None:
    if EelMessenger._instance is not None:
        EelMessenger._instance._handle_input(values)


@eel.expose
def handle_bool_input(value: bool) -> None:
    if EelMessenger._instance is not None:
        EelMessenger._instance._handle_bool_input(value)


@eel.expose
def handle_user_action(task_name: str, response: str) -> None:
    if EelMessenger._instance is not None:
        EelMessenger._instance._handle_action(task_name, response)


@eel.expose
def handle_command(task_name: str, command_name: str) -> None:
    if EelMessenger._instance is not None:
        EelMessenger._instance._handle_command(task_name, command_name)


# endregion


class EelMessenger(InputMessenger):
    _instance: Optional[EelMessenger] = None

    def __new__(cls, title: str, description: str):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, title: str, description: str) -> None:
        self._is_waiting_for_close = False
        self._is_main_thread_waiting_for_input = False
        self._close_event = Event()
        self._state_mutex = Lock()
        self._input_mutex = Lock()
        self._input_event = Event()
        self._action_item_events: Dict[str, Event] = {}
        self._action_item_responses: Dict[str, UserResponse] = {}
        self._commands: Dict[Tuple[str, str], Callable[[], None]] = {}

        # Call eel.init() in a blocking way, otherwise eel doesn't necessarily
        # have time to find all the exposed functions
        eel_directory = Path(__file__).parent.joinpath("web")
        eel.init(eel_directory.resolve().as_posix())
        gui_thread = Thread(
            name="EelMessenger",
            target=lambda: self._run_eel(title, description),
            daemon=True,
        )
        gui_thread.start()

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        with self._state_mutex:
            if self.is_closed:
                raise KeyboardInterrupt()
            eeli.log_status(task_name, index, status, message)

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        with self._state_mutex:
            if self.is_closed:
                raise KeyboardInterrupt()
            eeli.log_problem(task_name, level, message)

    def close(self, wait: bool):
        with self._state_mutex:
            self._is_waiting_for_close = True
        if wait:
            eeli.show_script_done_message()
        else:
            eeli.force_close()
        self._close_event.wait()

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> T:
        param = Parameter(display_name, parser, password, description=prompt)
        results = self.input_multiple({"param": param}, prompt="", title=title)
        return cast(T, results["param"])

    def input_bool(self, prompt: str, title: str = "") -> bool:
        with self._input_mutex:
            self._input_event.clear()
            with self._state_mutex:
                if self.is_closed:
                    # The event may have been set by the close handler just
                    # before this method called event.clear()
                    raise KeyboardInterrupt()
                if is_current_thread_main():
                    self._is_main_thread_waiting_for_input = True
            eeli.show_bool_input_dialog(prompt, title)
            self._input_event.wait()
            with self._state_mutex:
                if self.is_closed:
                    # The event may have been set by the close handler
                    raise KeyboardInterrupt()
                if is_current_thread_main():
                    self._is_main_thread_waiting_for_input = False
            return self._bool_input_value

    def _handle_bool_input(self, value: bool) -> None:
        self._bool_input_value = value
        self._input_event.set()

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        with self._input_mutex:
            with self._state_mutex:
                if self.is_closed:
                    raise KeyboardInterrupt()
                if is_current_thread_main():
                    self._is_main_thread_waiting_for_input = True
            error_message_by_name = {t: "" for t in params}
            output: Dict[str, object] = {}
            while True:
                self._input_event.clear()
                with self._state_mutex:
                    if self.is_closed:
                        # The event may have been set by the close handler just
                        # before this method called event.clear()
                        raise KeyboardInterrupt()
                eeli.show_input_dialog(title, prompt, params, error_message_by_name)
                self._input_event.wait()
                with self._state_mutex:
                    if self.is_closed:
                        # The event may have been set by the close handler
                        raise KeyboardInterrupt()
                value_by_name = self._input_values
                for name, value in value_by_name.items():
                    parser = params[name].parser
                    try:
                        val = parser(value)
                        error_message_by_name[name] = ""
                        output[name] = val
                    except ArgumentTypeError as e:
                        error_message_by_name[name] = f"Invalid input: {e}"
                    except Exception as e:
                        error_message_by_name[name] = f"An error occurred: {e}"
                if all([len(x) == 0 for x in error_message_by_name.values()]):
                    break
            with self._state_mutex:
                if is_current_thread_main():
                    self._is_main_thread_waiting_for_input = False
            return output

    def _handle_input(self, values: Dict[str, str]) -> None:
        self._input_values = values
        self._input_event.set()

    def wait(
        self, task_name: str, index: Optional[int], prompt: str, allow_retry: bool
    ) -> UserResponse:
        with self._state_mutex:
            if self.is_closed:
                raise KeyboardInterrupt()
            try:
                # This should always raise a KeyError because tasks are
                # assigned to exactly one thread and a single thread cannot
                # call wait() multiple times at exactly the same time. But set
                # the event anyway to avoid deadlocks.
                self._action_item_events[task_name].set()
            except KeyError:
                pass
            self._action_item_events[task_name] = Event()
            eeli.add_action_item(task_name, index, prompt, allow_retry)
        self._action_item_events[task_name].wait()
        with self._state_mutex:
            # The event may have been set by the close handler
            if self.is_closed:
                raise KeyboardInterrupt()
            eeli.remove_action_item(task_name)
            try:
                del self._action_item_events[task_name]
            except KeyError:
                pass
            try:
                response = self._action_item_responses[task_name]
                del self._action_item_responses[task_name]
                return response
            except KeyError:
                # Response should always be set by the handler function, but
                # set a default just in case. Default to DONE rather than RETRY
                # so the script doesn't get stuck in an infinite loop.
                return UserResponse.DONE

    def _handle_action(self, task_name: str, response: str) -> None:
        with self._state_mutex:
            response = response.lower()
            if response == "retry":
                self._action_item_responses[task_name] = UserResponse.RETRY
            else:
                self._action_item_responses[task_name] = UserResponse.DONE
            try:
                self._action_item_events[task_name].set()
            except KeyError:
                return

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        with self._state_mutex:
            if self.is_closed:
                raise KeyboardInterrupt()
            self._commands[task_name, command_name] = callback
            eeli.add_command(task_name, command_name)

    def _handle_command(self, task_name: str, command_name: str) -> None:
        with self._state_mutex:
            try:
                callback = self._commands[task_name, command_name]
            except KeyError:
                return
        callback()

    def remove_command(self, task_name: str, command_name: str) -> None:
        with self._state_mutex:
            if self.is_closed:
                raise KeyboardInterrupt()
            eeli.remove_command(task_name, command_name)
            try:
                del self._commands[task_name, command_name]
            except KeyError:
                pass

    @property
    def is_closed(self) -> bool:
        # Don't acquire the state mutex here because the caller may have already
        # done it.
        return self._close_event.is_set()

    def _run_eel(self, title: str, description: str) -> None:
        eeli.set_title(title)
        eeli.set_description(description)
        eel.start("index.html", close_callback=self._handle_close)

    def _handle_close(self, *_args: object, **_kwargs: object) -> None:
        with self._state_mutex:
            # If the user closed the window at some random time, the client
            # should be informed so the script can be shut down. Interrupt the
            # main thread in the same way as for CTRL+C for consistency.
            # No need to interrupt the main thread if it already called close
            # because the window being closed is expected.
            # No need to interrupt the main thread if it's waiting for input
            # because the input method itself will raise a KeyboardInterrupt.
            if not (
                self._is_waiting_for_close or self._is_main_thread_waiting_for_input
            ):
                interrupt_main_thread()
            self._close_event.set()
            # Release waiting threads so they can exit cleanly
            for e in self._action_item_events.values():
                e.set()
            self._input_event.set()
