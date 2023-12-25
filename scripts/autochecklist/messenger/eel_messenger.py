# pyright: reportPrivateUsage=false

from __future__ import annotations

import typing
from argparse import ArgumentTypeError
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Dict, Optional, Set, Tuple, TypeVar

import eel

from . import eel_interface as eeli
from .input_messenger import (
    InputMessenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
    UserResponse,
)

T = TypeVar("T")


# region: Callbacks to be used by the JavaScript frontend


@eel.expose
def handle_input(key: int, values: Dict[str, str]) -> None:
    instance = EelMessenger._instance
    if instance is None:
        return
    # Run the handler in a separate thread to avoid blocking the main eel
    # thread
    thread = Thread(
        target=lambda: instance._handle_input(key, values),
        daemon=True,
    )
    thread.start()


@eel.expose
def handle_bool_input(key: int, value: bool) -> None:
    instance = EelMessenger._instance
    if instance is None:
        return
    # Run the handler in a separate thread to avoid blocking the main eel
    # thread
    thread = Thread(
        target=lambda: instance._handle_bool_input(key, value),
        daemon=True,
    )
    thread.start()


@eel.expose
def handle_user_action(task_name: str, response: str) -> None:
    instance = EelMessenger._instance
    if instance is None:
        return
    # Run the handler in a separate thread to avoid blocking the main eel
    # thread
    thread = Thread(
        target=lambda: instance._handle_action_item_response(task_name, response),
        daemon=True,
    )
    thread.start()


# TODO: Handle the user pressing the command button multiple times
@eel.expose
def handle_command(task_name: str, command_name: str) -> None:
    # The command handler runs an arbitrary callback, which might get
    # deadlocked. Run it in a separate thread so that it doesn't deadlock the
    # entire GUI, at least.
    instance = EelMessenger._instance
    if instance is None:
        return

    def run_handler():
        try:
            instance._handle_command(task_name, command_name)
        except KeyboardInterrupt:
            # The EelMessenger might shut down before the callback completes.
            # There's no point in dumping a stack trace to the console over
            # that.
            pass

    thread = Thread(target=run_handler, daemon=True)
    thread.start()


# endregion


class EelMessenger(InputMessenger):
    _instance: Optional[EelMessenger] = None

    def __new__(cls, title: str, description: str):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, title: str, description: str) -> None:
        self._title = title
        self._description = description

        self._state_mutex = Lock()
        self._start_event = Event()
        self._close_event = Event()
        self._input_event_by_key: Dict[int, Event] = {}
        self._input_by_key: Dict[int, object] = {}
        self._action_item_events: Dict[str, Event] = {}
        self._action_item_responses: Dict[str, UserResponse] = {}
        self._callback_by_command: Dict[Tuple[str, str], Callable[[], None]] = {}
        self._current_key = 0
        self._key_lock = Lock()

    def run_main_loop(self) -> None:
        # Call eel.init() in a blocking way, otherwise eel doesn't necessarily
        # have time to find all the exposed functions
        eel_directory = Path(__file__).parent.joinpath("web")
        eel.init(eel_directory.resolve().as_posix())
        self._start_event.set()
        eeli.set_title(self._title)
        eeli.set_description(self._description)
        eel.start("index.html", close_callback=self._handle_close)
        # TODO: start never seems to return! Possibly a deadlock in the cancel
        # callback when it calls input_bool()

    def wait_for_start(self) -> None:
        self._start_event.wait()

    @property
    def is_closed(self) -> bool:
        # Don't acquire the state mutex here because the caller may have already
        # done it.
        return self._close_event.is_set()

    def close(self):
        if self.is_closed:
            return
        else:
            eeli.show_script_done_message()
            self._close_event.wait()

    def _handle_close(self, *_args: object, **_kwargs: object) -> None:
        with self._state_mutex:
            self._start_event.set()
            self._close_event.set()
            # Release waiting threads so they can exit cleanly
            for e in self._action_item_events.values():
                e.set()
            for e in self._input_event_by_key.values():
                e.set()

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        if self.is_closed:
            raise KeyboardInterrupt()
        eeli.log_status(task_name, index, status, message)

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        if self.is_closed:
            raise KeyboardInterrupt()
        eeli.log_problem(task_name, level, message)

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
        return typing.cast(T, results["param"])

    def input_bool(self, prompt: str, title: str = "") -> bool:
        if self.is_closed:
            raise KeyboardInterrupt()
        key = self._get_unique_key()
        with self._state_mutex:
            input_received_event = Event()
            self._input_event_by_key[key] = input_received_event
        eeli.show_bool_input_dialog(key, prompt, title)
        input_received_event.wait()
        with self._state_mutex:
            if self.is_closed:
                # The event may have been set by the close handler.
                # Don't bother cleaning up the event and input since this means
                # the script is shutting down anyway.
                raise KeyboardInterrupt()
            choice = typing.cast(bool, self._input_by_key[key])
            del self._input_by_key[key]
            del self._input_event_by_key[key]
        return choice

    def _handle_bool_input(self, key: int, value: bool) -> None:
        with self._state_mutex:
            try:
                self._input_by_key[key] = value
                self._input_event_by_key[key].set()
            except KeyError:
                # Should never happen, unless the JavaScript frontend is
                # sending invalid messages
                pass

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        if self.is_closed:
            raise KeyboardInterrupt()
        key = self._get_unique_key()
        with self._state_mutex:
            input_received_event = Event()
            self._input_event_by_key[key] = input_received_event
        error_message_by_name = {t: "" for t in params}
        output: Dict[str, object] = {}
        while True:
            eeli.show_input_dialog(key, title, prompt, params, error_message_by_name)
            input_received_event.wait()
            with self._state_mutex:
                # This check does need to be protected by the state mutex,
                # otherwise the close handler may set the event but then have
                # this method clear it and then wait indefinitely.
                if self.is_closed:
                    # The event may have been set by the close handler.
                    # Don't bother cleaning up the event and input since this
                    # means the script is shutting down anyway.
                    raise KeyboardInterrupt()
                input_received_event.clear()
                value_by_name = typing.cast(Dict[str, str], self._input_by_key[key])
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
            if all([x == "" for x in error_message_by_name.values()]):
                break
        with self._state_mutex:
            del self._input_by_key[key]
            del self._input_event_by_key[key]
        return output

    def _handle_input(self, key: int, values: Dict[str, str]) -> None:
        with self._state_mutex:
            try:
                # TODO: What if the JavaScript doesn't return a value for every
                # name?
                self._input_by_key[key] = values
                self._input_event_by_key[key].set()
            except KeyError:
                # Should never happen, unless the JavaScript frontend is
                # sending invalid messages
                pass

    def wait(
        self,
        task_name: str,
        index: Optional[int],
        prompt: str,
        allowed_responses: Set[UserResponse],
    ) -> UserResponse:
        if self.is_closed:
            raise KeyboardInterrupt()
        with self._state_mutex:
            try:
                # This should always raise a KeyError because tasks are
                # assigned to exactly one thread and a single thread cannot
                # call wait() multiple times at exactly the same time. But set
                # the event anyway, just in case, to avoid a method getting
                # stuck waiting indefinitely.
                self._action_item_events[task_name].set()
            except KeyError:
                pass
            response_received_event = Event()
            self._action_item_events[task_name] = response_received_event
        eeli.add_action_item(task_name, index, prompt, allowed_responses)
        response_received_event.wait()
        with self._state_mutex:
            # The event may have been set by the close handler
            if self.is_closed:
                raise KeyboardInterrupt()
            try:
                del self._action_item_events[task_name]
            except KeyError:
                pass
            try:
                response = self._action_item_responses[task_name]
                del self._action_item_responses[task_name]
            except KeyError:
                # Response should always be set by the handler function, but
                # set a default just in case. Default to DONE rather than RETRY
                # so the script doesn't get stuck in an infinite loop.
                response = UserResponse.DONE
            return response

    def _handle_action_item_response(self, task_name: str, response: str) -> None:
        response = response.lower()
        with self._state_mutex:
            if response == "retry":
                self._action_item_responses[task_name] = UserResponse.RETRY
            elif response == "skip":
                self._action_item_responses[task_name] = UserResponse.SKIP
            elif response == "done":
                self._action_item_responses[task_name] = UserResponse.DONE
            try:
                self._action_item_events[task_name].set()
            except KeyError:
                pass

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        if self.is_closed:
            raise KeyboardInterrupt()
        with self._state_mutex:
            self._callback_by_command[task_name, command_name] = callback
        eeli.add_command(task_name, command_name)

    def _handle_command(self, task_name: str, command_name: str) -> None:
        with self._state_mutex:
            try:
                callback = self._callback_by_command[task_name, command_name]
            except KeyError:
                return
        callback()

    def remove_command(self, task_name: str, command_name: str) -> None:
        if self.is_closed:
            raise KeyboardInterrupt()
        eeli.remove_command(task_name, command_name)
        with self._state_mutex:
            try:
                del self._callback_by_command[task_name, command_name]
            except KeyError:
                pass

    def create_progress_bar(
        self, display_name: str, max_value: float, units: str
    ) -> int:
        return eeli.create_progress_bar(display_name, max_value, units)

    def update_progress_bar(self, key: int, progress: float) -> None:
        eeli.update_progress_bar(key, progress)

    def delete_progress_bar(self, key: int) -> None:
        eeli.delete_progress_bar(key)

    def _get_unique_key(self) -> int:
        with self._key_lock:
            self._current_key += 1
            return self._current_key
