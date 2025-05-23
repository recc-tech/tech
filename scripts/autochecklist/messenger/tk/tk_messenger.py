# pyright: reportUnnecessaryTypeIgnoreComment=information
# This is needed so platform-specific code (subprocess.CREATE_NO_WINDOW) can type-check
from __future__ import annotations

import ctypes
import platform
import subprocess
import sys
import threading
import tkinter
import typing
from argparse import ArgumentTypeError
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Lock
from tkinter import Canvas, Menu, Misc, PhotoImage, Tk, Toplevel, messagebox
from tkinter.ttk import Button, Entry, Frame, Label, Style
from typing import Callable, Dict, List, Literal, Optional, Set, Tuple, TypeVar

from ...base_config import BaseConfig
from ..input_messenger import (
    InputMessenger,
    ListChoice,
    Parameter,
    ProblemLevel,
    TaskStatus,
    UserResponse,
)
from .list_input_dialog import ListInputDialog
from .progress_bar_group import ProgressBarGroup
from .responsive_textbox import ResponsiveTextbox
from .scrollable_frame import ScrollableFrame
from .yes_no_dialog import YesNoDialog

T = TypeVar("T")

_NORMAL_FONT = "Calibri 12"
_ITALIC_FONT = f"{_NORMAL_FONT} italic"
_BOLD_FONT = f"{_NORMAL_FONT} bold"
_H2_FONT = "Calibri 18 bold"


class TkMessenger(InputMessenger):
    """Tkinter-based user interface."""

    _QUEUE_EVENT = "<<TaskQueued>>"

    def __init__(
        self,
        title: str,
        description: str,
        confirm_exit_message: str,
        config: BaseConfig,
        *,
        theme: Literal["dark", "light"],
        show_statuses_by_default: bool,
        icon: Optional[Path] = None,
        auto_close: bool = False,
    ) -> None:
        """
        Initialize a `TkMessenger` object, but do not show the GUI yet.
        """
        self._title = title
        self._description = description
        self._confirm_exit_message = confirm_exit_message
        self._config = config
        self._show_statuses_by_default = show_statuses_by_default
        self._icon = icon
        self._auto_close = auto_close
        self._background = "#323232" if theme == "dark" else "#EEEEEE"
        self._foreground = "#FFFFFF" if theme == "dark" else "#000000"
        self._light_foreground = "#888888"

        self._start_event = threading.Event()
        self._end_event = threading.Event()
        self._is_script_done = False
        self._close_confirm = Lock()
        self._num_problems = 0
        self._mutex = Lock()
        self._waiting_events: Set[threading.Event] = set()
        self._queue: Queue[_GuiTask] = Queue()

    def run_main_loop(self) -> None:
        """
        Show the GUI and run the main loop.
        This should be called from the main thread.
        """
        try:
            self._create_gui()
            self._tk.after(0, lambda: self._start_event.set())
            self._tk.mainloop()
        finally:
            # Release all waiting threads so they can exit cleanly
            for e in self._waiting_events:
                e.set()
            self._start_event.set()
            self._end_event.set()

    def _handle_queued_task(self) -> None:
        try:
            task = self._queue.get()
            task.run()
            if task.update_scrollregion:
                self._handle_update_scrollregion()
        except Exception as e:
            print(f"Exception in custom event handler: {e}", file=sys.stderr)

    def wait_for_start(self) -> None:
        """Wait until the GUI has appeared and the main loop has started."""
        self._start_event.wait()

    @property
    def is_closed(self) -> bool:
        """Whether the GUI has been closed."""
        return self._end_event.is_set()

    def close(self) -> None:
        """
        This should be called *by the script* once it is done (i.e., all tasks
        have been completed).
        The window will not necessarily be closed immediately.
        """

        def show_goodbye_message() -> None:
            self._action_items_section.set_message(
                "All done :D Close this window to exit."
            )

        with self._mutex:
            error_count = self._num_problems

        if self.is_closed:
            return
        if self._auto_close and error_count == 0:
            self._exit()
        else:
            self._is_script_done = True
            self._tk.after_idle(show_goodbye_message)
            self._end_event.wait()

    def _handle_exit(self):
        """
        Called when the user presses the "x" button to close the window.
        """
        if self._is_script_done:
            # If all tasks are done, no need to wait
            should_exit = True
        elif self._close_confirm.acquire(blocking=False):
            # The user clicked "x" just once and the script is not done.
            # Ask for confirmation.
            try:
                should_exit = self.input_bool(
                    title="Confirm exit",
                    prompt=self._confirm_exit_message,
                )
            finally:
                self._close_confirm.release()
        else:
            # The user clicked twice in a row, so go ahead and exit.
            should_exit = True
        if should_exit:
            self._exit()

    def _exit(self) -> None:
        """Actually close the UI and end the program."""

        def do_exit():
            self._end_event.set()
            self._tk.destroy()

        self._tk.after_idle(do_exit)

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        """Report the progress of a task."""
        if self.is_closed:
            raise KeyboardInterrupt()

        def do_log_status() -> None:
            self._task_statuses_grid.upsert_row(
                index=index, task_name=task_name, status=status, message=message
            )

        self._queue.put(_GuiTask(do_log_status, update_scrollregion=True))
        self._tk.event_generate(self._QUEUE_EVENT)

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        """Report that a problem has occurred."""
        if self.is_closed:
            raise KeyboardInterrupt()
        with self._mutex:
            self._num_problems += 1

        def do_log_problem() -> None:
            self._problems_frame.grid()
            self._problems_grid.add_row(task_name, level, message)

        self._queue.put(_GuiTask(do_log_problem, update_scrollregion=True))
        self._tk.event_generate(self._QUEUE_EVENT)

    def input(
        self,
        display_name: str,
        password: bool,
        parser: Callable[[str], T] = lambda x: x,
        prompt: str = "",
        title: str = "",
    ) -> T:
        """Request a single input from the user."""
        param = Parameter(display_name, parser, password, description=prompt)
        results = self.input_multiple({"param": param}, prompt="", title=title)
        return typing.cast(T, results["param"])

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        """Request multiple inputs from the user at once."""

        def handle_submit() -> None:
            submit_event.set()

        def handle_close() -> None:
            nonlocal was_input_cancelled
            should_exit = self.input_bool(
                title="Confirm close",
                prompt="Are you sure you want to close the input dialog? This will interrupt whatever task was expecting input.",
            )
            if not should_exit:
                return
            was_input_cancelled = True
            submit_event.set()

        def create_input_dialog() -> None:
            nonlocal input_frame, entry_by_key, error_label_by_key, submit_button
            (
                input_frame,
                entry_by_key,
                error_label_by_key,
                submit_button,
            ) = self._create_input_dialog(title=title, prompt=prompt, params=params)
            input_frame.protocol("WM_DELETE_WINDOW", handle_close)
            submit_button.bind("<Button-1>", lambda _: handle_submit())

        def freeze_and_read_input_dialog() -> None:
            submit_button.configure(state="disabled")
            for key, entry in entry_by_key.items():
                entry.configure(state="disabled")
                input_by_key[key] = entry.get()
            dialog_frozen_event.set()

        def update_and_unfreeze_input_dialog(error_by_key: Dict[str, str]) -> None:
            for key, label in error_label_by_key.items():
                label.set_text(error_by_key[key])
            for entry in entry_by_key.values():
                entry.configure(state="enabled")
            submit_button.configure(state="enabled")

        def hide_input_dialog() -> None:
            input_frame.destroy()

        if self.is_closed:
            raise KeyboardInterrupt()

        submit_event = threading.Event()
        dialog_frozen_event = threading.Event()
        was_input_cancelled = False
        input_frame: Toplevel
        entry_by_key: Dict[str, Entry]
        error_label_by_key: Dict[str, ResponsiveTextbox]
        submit_button: Button
        input_by_key = {key: "" for key in params}
        parser_by_key = {key: p.parser for key, p in params.items()}

        self._queue.put(_GuiTask(create_input_dialog, update_scrollregion=False))
        self._tk.event_generate(self._QUEUE_EVENT)
        try:
            while True:
                self._wait_and_clear_event(submit_event)
                # Make sure the user can't submit multiple times or edit the fields
                # while they're being processed
                self._queue.put(
                    _GuiTask(freeze_and_read_input_dialog, update_scrollregion=False)
                )
                self._tk.event_generate(self._QUEUE_EVENT)
                self._wait_and_clear_event(dialog_frozen_event)
                # In case the user clicked twice before the dialog was frozen
                submit_event.clear()
                if was_input_cancelled:
                    raise InputCancelledException("The user closed the input dialog.")
                output_by_key, error_by_key = self._parse_inputs(
                    input_by_key, parser_by_key
                )
                if all(e == "" for e in error_by_key.values()):
                    break
                else:
                    self._queue.put(
                        _GuiTask(
                            lambda: update_and_unfreeze_input_dialog(error_by_key),
                            update_scrollregion=False,
                        )
                    )
                    self._tk.event_generate(self._QUEUE_EVENT)
            return output_by_key
        finally:
            self._queue.put(_GuiTask(hide_input_dialog, update_scrollregion=False))
            self._tk.event_generate(self._QUEUE_EVENT)

    def _parse_inputs(
        self,
        input_by_key: Dict[str, str],
        parser_by_key: Dict[str, Callable[[str], T]],
    ) -> Tuple[Dict[str, Optional[T]], Dict[str, str]]:
        output_by_key: Dict[str, Optional[T]] = {key: None for key in input_by_key}
        error_by_key: Dict[str, str] = {key: "" for key in input_by_key}
        for key, value in input_by_key.items():
            try:
                parse = parser_by_key[key]
                output_by_key[key] = parse(value)
            except KeyboardInterrupt:
                raise
            except ArgumentTypeError as e:
                error_by_key[key] = f"Invalid input: {e}"
            except BaseException as e:
                error_by_key[key] = f"An error occurred during parsing: {e}"
        return output_by_key, error_by_key

    def input_bool(self, prompt: str, title: str = "") -> bool:
        """Ask the user a yes/no question."""
        w = None
        try:
            w = YesNoDialog(
                self._tk,
                title=title,
                prompt=prompt,
                default_answer="no",
                background=self._background,
                foreground=self._foreground,
                font=_NORMAL_FONT,
                padx=10,
                pady=10,
            )
            _position_toplevel(self._tk, w)
            return w.wait_for_answer()
        finally:
            if w:
                w.destroy()

    def input_from_list(
        self, choices: List[ListChoice[T]], prompt: str, title: str = ""
    ) -> Optional[T]:
        choice = None
        submit_event = threading.Event()

        def create_dialog() -> None:
            nonlocal choice
            w = None
            try:
                w = ListInputDialog(
                    self._tk,
                    title=title,
                    prompt=prompt,
                    choices=choices,
                    background=self._background,
                    foreground=self._foreground,
                    font=_NORMAL_FONT,
                    padx=10,
                    pady=10,
                )
                _position_toplevel(self._tk, w)
                choice = w.wait_for_answer()
            finally:
                submit_event.set()
                if w:
                    w.destroy()

        self._queue.put(_GuiTask(create_dialog, update_scrollregion=False))
        self._tk.event_generate(self._QUEUE_EVENT)

        self._wait_and_clear_event(submit_event)
        return choice

    def wait(
        self,
        task_name: str,
        index: Optional[int],
        prompt: str,
        allowed_responses: Set[UserResponse],
    ) -> UserResponse:
        """
        Wait for the user to confirm that they have completed a task manually,
        to request that the task automation be re-run, etc.
        """
        if self.is_closed:
            raise KeyboardInterrupt()

        click_event = threading.Event()
        response: Optional[UserResponse] = None
        actual_index = index or -1

        def handle_click_done() -> None:
            nonlocal response
            # Keep the first choice if the user somehow presses both quickly
            response = response or UserResponse.DONE
            click_event.set()

        def handle_click_retry() -> None:
            nonlocal response
            response = response or UserResponse.RETRY
            click_event.set()

        def handle_click_skip() -> None:
            nonlocal response
            should_skip = self.input_bool(
                title="Confirm skip",
                prompt="Are you sure you want to skip this task?",
            )
            if not should_skip:
                return
            response = response or UserResponse.SKIP
            click_event.set()

        def do_add_action_item() -> None:
            nonlocal actual_index
            on_click_done = (
                handle_click_done if UserResponse.DONE in allowed_responses else None
            )
            on_click_retry = (
                handle_click_retry if UserResponse.RETRY in allowed_responses else None
            )
            on_click_skip = (
                handle_click_skip if UserResponse.SKIP in allowed_responses else None
            )
            actual_index = self._action_items_section.add_row(
                index,
                task_name,
                prompt,
                on_click_done=on_click_done,
                on_click_retry=on_click_retry,
                on_click_skip=on_click_skip,
            )

        def do_remove_action_item() -> None:
            self._action_items_section.delete_row(actual_index)

        self._queue.put(_GuiTask(do_add_action_item, update_scrollregion=True))
        self._tk.event_generate(self._QUEUE_EVENT)
        self._wait_and_clear_event(click_event)
        self._queue.put(_GuiTask(do_remove_action_item, update_scrollregion=True))
        self._tk.event_generate(self._QUEUE_EVENT)

        # Response should always be set here because the button click handlers
        # set it, but set a default just in case. Default to DONE rather than
        # RETRY so the script doesn't get stuck in an infinite loop.
        return response or UserResponse.DONE

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        """
        Add a command related to a specific task (e.g., to cancel that task).
        """

        def do_add_command() -> None:
            self._task_statuses_grid.upsert_command(task_name, command_name, callback)

        self._queue.put(_GuiTask(do_add_command, update_scrollregion=False))
        self._tk.event_generate(self._QUEUE_EVENT)

    def remove_command(self, task_name: str, command_name: str) -> None:
        """Remove a previously-added task-specific command."""

        def do_remove_command() -> None:
            self._task_statuses_grid.remove_command(task_name, command_name)

        self._queue.put(_GuiTask(do_remove_command, update_scrollregion=False))
        self._tk.event_generate(self._QUEUE_EVENT)

    def create_progress_bar(
        self, display_name: str, max_value: float, units: str
    ) -> int:
        return self._progress_bar_group.create_progress_bar(
            display_name, max_value, units
        )

    def update_progress_bar(self, key: int, progress: float) -> None:
        self._progress_bar_group.update_progress_bar(key, progress)

    def delete_progress_bar(self, key: int) -> None:
        self._progress_bar_group.delete_progress_bar(key)

    def _handle_update_scrollregion(self) -> None:
        # Make sure the display has updated before recomputing the scrollregion size
        self._tk.update_idletasks()
        canvas = typing.cast(Canvas, self._scroll_frame.master)
        region = canvas.bbox("all")
        canvas.config(scrollregion=region)

    def _reload_config(self) -> None:
        """
        Called when the user presses the "Reload Config" button.
        """
        try:
            self._config.reload()
        except Exception as e:
            self.log_problem(
                task_name="RELOAD CONFIG",
                level=ProblemLevel.ERROR,
                message=f"Failed to reload config: {e}",
            )
            return
        now = datetime.now()
        self._last_reload_textbox.set_text(
            f"[[styled|rjust|Last reload: {now.strftime('%H:%M:%S')}]]"
        )

    def _create_gui(self) -> None:
        """Build the `Tk` object to be used for the GUI."""
        # Try to make the GUI less blurry
        try:
            windll = ctypes.windll  # pyright: ignore[reportAttributeAccessIssue]
            windll.shcore.SetProcessDpiAwareness(1)
        except AttributeError:
            # windll is only available on Windows
            if platform.system() == "Windows":
                raise

        self._tk = Tk()
        self._tk.title(self._title)
        if self._icon is not None:
            icon_img = PhotoImage(file=self._icon.resolve().as_posix())
            self._tk.iconphoto(True, icon_img)
        screen_height = self._tk.winfo_screenheight()
        # Apparently tk.winfo_screenwidth() doesn't work very well on
        # multi-monitor setups
        approx_screen_width = 16 * screen_height / 9
        window_width = int(approx_screen_width * 0.75)
        window_height = int(screen_height * 0.75)
        x = int((approx_screen_width - window_width) / 2)
        y = (screen_height - window_height) // 2
        self._tk.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self._scroll_frame = ScrollableFrame(
            self._tk,
            padding=25,
            background=self._background,
            scrollbar_width=25,
        )
        self._scroll_frame.outer_frame.pack(fill="both", expand=1)
        self._scroll_frame.columnconfigure(index=0, weight=1)

        # -------------------- Behaviour --------------------

        self._tk.protocol("WM_DELETE_WINDOW", self._handle_exit)
        self._right_click_menu = self._create_right_click_menu()
        self._progress_bar_group = ProgressBarGroup(
            self._tk,
            padx=10,
            pady=10,
            width=int(0.5 * window_width),
            background=self._background,
            foreground=self._foreground,
            font=_NORMAL_FONT,
        )
        self._tk.bind_all(sequence="<Button-3>", func=self._show_right_click_menu)
        self._tk.bind_all(self._QUEUE_EVENT, func=lambda _: self._handle_queued_task())

        # -------------------- Style --------------------

        self._tk.config(background=self._background)
        style = Style()
        style.configure(
            "TButton",
            font=_NORMAL_FONT,
        )
        style.configure(
            "TFrame",
            background=self._background,
            foreground=self._foreground,
        )

        WIDTH = 170

        # -------------------- Description, reload config --------------------

        header_frame = Frame(self._scroll_frame)
        header_frame.grid(sticky="NEW")
        header_frame.columnconfigure(index=0, weight=1)
        header_frame.columnconfigure(index=1, weight=0)

        if self._description.strip():
            description_textbox = ResponsiveTextbox(
                header_frame,
                width=WIDTH,
                font=_ITALIC_FONT,
                background=self._background,
                foreground=self._light_foreground,
            )
            description_textbox.grid(sticky="NE", row=0, column=0)
            description_textbox.set_text(self._description)

        reload_config_frame = Frame(header_frame, borderwidth=2)
        reload_config_frame.grid(sticky="NEW", row=0, column=1)

        reload_config_btn = Button(
            reload_config_frame,
            text="Reload Config",
            command=self._reload_config,
        )
        reload_config_btn.grid(sticky="NE")
        self._last_reload_textbox = ResponsiveTextbox(
            reload_config_frame,
            width=20,
            font=_ITALIC_FONT,
            background=self._background,
            foreground=self._light_foreground,
        )
        self._last_reload_textbox.grid(sticky="NE")

        # -------------------- Action items section --------------------

        self._action_items_frame = Frame(self._scroll_frame)
        self._action_items_frame.grid(sticky="NEW", pady=(75, 0))
        self._action_items_frame.columnconfigure(index=0, weight=1)

        self._action_items_section = _ActionItemSection(
            self._action_items_frame,
            initial_message="Some automatic tasks are running. Please wait.",
            outer_padding=5,
            padx=5,
            pady=5,
            background=self._background,
            foreground=self._foreground,
            normal_font=_NORMAL_FONT,
            header_font=_BOLD_FONT,
        )
        self._action_items_section.grid(sticky="NEW")

        # -------------------- Problems section --------------------

        self._problems_frame = Frame(self._scroll_frame)
        self._problems_frame.grid(sticky="NEW")
        self._problems_frame.columnconfigure(index=0, weight=1)

        problems_header = ResponsiveTextbox(
            self._problems_frame,
            width=WIDTH,
            font=_H2_FONT,
            background=self._background,
            foreground=self._foreground,
        )
        problems_header.grid(sticky="NEW", pady=(75, 0))
        problems_header.set_text("Problems")

        self._problems_grid = _ProblemGrid(
            self._problems_frame,
            outer_padding=5,
            padx=5,
            pady=5,
            background=self._background,
            foreground=self._foreground,
            normal_font=_NORMAL_FONT,
            header_font=_BOLD_FONT,
            bold_font=_BOLD_FONT,
        )
        self._problems_grid.grid(sticky="NEW")

        # -------------------- Task statuses section --------------------

        task_statuses_header_frame = Frame(self._scroll_frame)
        task_statuses_header_frame.grid(sticky="NEW")
        task_statuses_header_frame.columnconfigure(index=0, weight=1)

        task_statuses_header = ResponsiveTextbox(
            task_statuses_header_frame,
            width=13,
            font=_H2_FONT,
            background=self._background,
            foreground=self._foreground,
        )
        task_statuses_header.grid(sticky="NEW", pady=(75, 0), row=0, column=0)
        task_statuses_header.set_text("Task Statuses")

        def show_task_statuses() -> None:
            self._queue.put(_GuiTask(do_show_task_statuses, update_scrollregion=True))
            self._tk.event_generate(self._QUEUE_EVENT)

        def do_show_task_statuses() -> None:
            self._task_statuses_grid.grid()
            task_statuses_showhide_btn.configure(
                text="Hide", command=hide_task_statuses
            )

        def hide_task_statuses() -> None:
            self._queue.put(_GuiTask(do_hide_task_statuses, update_scrollregion=True))
            self._tk.event_generate(self._QUEUE_EVENT)

        def do_hide_task_statuses() -> None:
            self._task_statuses_grid.grid_remove()
            task_statuses_showhide_btn.configure(
                text="Show", command=show_task_statuses
            )

        task_statuses_showhide_btn = Button(task_statuses_header_frame)
        task_statuses_showhide_btn.grid(sticky="NEW", pady=(75, 0), row=0, column=1)

        self._task_statuses_grid = _TaskStatusGrid(
            self._scroll_frame,
            outer_padding=5,
            padx=5,
            pady=5,
            background=self._background,
            foreground=self._foreground,
            normal_font=_NORMAL_FONT,
            header_font=_BOLD_FONT,
            bold_font=_BOLD_FONT,
        )
        self._task_statuses_grid.grid(sticky="NEW")

        # Leave this frame hidden until necessary
        self._problems_frame.grid_remove()
        # Start with task status section collapsed
        if self._show_statuses_by_default:
            show_task_statuses()
        else:
            hide_task_statuses()

    def _create_input_dialog(
        self, title: str, prompt: str, params: Dict[str, Parameter]
    ) -> Tuple[Toplevel, Dict[str, Entry], Dict[str, ResponsiveTextbox], Button]:
        """
        Create the popup window to be used for taking input.
        """
        entry_by_name: Dict[str, Entry] = {}
        error_message_by_name: Dict[str, ResponsiveTextbox] = {}
        w = Toplevel(self._tk, padx=10, pady=10, background=self._background)
        try:
            w.rowconfigure(index=1, weight=1)
            w.columnconfigure(index=0, weight=1)
            w.title(title)
            if prompt:
                prompt_box = Label(
                    w,
                    text=prompt,
                    font=_ITALIC_FONT,
                    padding=(0, 0, 0, 50),
                    background=self._background,
                    foreground=self._foreground,
                )
                prompt_box.grid()
            for name, param in params.items():
                param_frame = Frame(w, borderwidth=1)
                param_frame.grid(pady=15, sticky="NSEW")
                param_frame.columnconfigure(index=0, weight=1)
                entry_row = Frame(param_frame)
                entry_row.grid(sticky="NEW")
                entry_row.columnconfigure(index=0, weight=1)
                entry_row.columnconfigure(index=1, weight=2)
                name_label = Label(
                    entry_row,
                    text=param.display_name,
                    font=_BOLD_FONT,
                    background=self._background,
                    foreground=self._foreground,
                )
                name_label.grid(row=0, column=0, padx=5, sticky="NEW")
                entry = Entry(
                    entry_row,
                    show="*" if param.password else "",
                    font=_NORMAL_FONT,
                )
                entry.grid(row=0, column=1, padx=5, sticky="NEW")
                if param.default:
                    entry.insert(0, param.default)
                entry_by_name[name] = entry
                if param.description:
                    description_box = ResponsiveTextbox(
                        param_frame,
                        width=20,
                        font=_ITALIC_FONT,
                        background=self._background,
                        foreground=self._foreground,
                    )
                    description_box.grid(sticky="NEW")
                    description_box.set_text(param.description)
                error_message = ResponsiveTextbox(
                    param_frame,
                    width=20,
                    font=_NORMAL_FONT,
                    background=self._background,
                    foreground="red",
                )
                error_message.grid(sticky="NEW")
                error_message_by_name[name] = error_message
            btn = Button(w, text="Done")
            btn.grid()
            _position_toplevel(self._tk, w)
            return (w, entry_by_name, error_message_by_name, btn)
        except:
            w.destroy()
            raise

    def _create_right_click_menu(self) -> Menu:
        """
        Create the right-click context menu, but do not show it yet.
        """
        menu = Menu(None, tearoff=0)
        menu.add_command(label="Copy")
        menu.add_command(label="Open in Notepad++")
        return menu

    def _show_right_click_menu(self, event: tkinter.Event[Misc]):
        """
        Show the right-click context menu.
        """

        def try_copy(text: str) -> None:
            try:
                self._tk.clipboard_clear()
                self._tk.clipboard_append(text)
            except Exception as e:
                messagebox.showwarning(
                    title="Failed to copy",
                    message="An error occurred. Please try again.",
                )
                print(e)

        def try_open_in_notepadpp(path: Path) -> None:
            try:
                # Use Popen so this doesn't block
                subprocess.Popen(["notepad++.exe", path.as_posix()])
            except Exception as e:
                messagebox.showwarning(
                    title="Failed to open in Notepad++",
                    message="An error occurred. Please try again.",
                )
                print(e)

        try:
            # If nothing is selected, this should raise a TclError.
            # For some reason, that doesn't seem to happen after you click
            # from one _CopyableText widget to another :(
            # If you click elsewhere, selection_get still returns the
            # previously-selected text.
            # Other functions like selection_own_get().get("sel.first",
            # "sel.last") also return the previously-selected text.
            selected_text = str(self._tk.selection_get())
        except Exception:
            selected_text = ""
        self._right_click_menu.entryconfig(
            "Copy",
            state="normal" if selected_text else "disabled",
            command=lambda: try_copy(selected_text),
        )
        path = Path(selected_text)
        can_be_opened = selected_text and (
            path.is_file()
            or (not path.is_dir() and path.is_absolute() and path.parent.is_dir())
        )
        self._right_click_menu.entryconfig(
            "Open in Notepad++",
            state="normal" if can_be_opened else "disabled",
            command=lambda: try_open_in_notepadpp(path),
        )
        self._right_click_menu.tk_popup(x=event.x_root, y=event.y_root)

    def _wait_and_clear_event(self, event: threading.Event) -> None:
        with self._mutex:
            self._waiting_events.add(event)
        event.wait()
        event.clear()
        with self._mutex:
            self._waiting_events.remove(event)
        if self.is_closed:
            raise KeyboardInterrupt()


@dataclass
class _GuiTask:
    run: Callable[[], None]
    update_scrollregion: bool


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
        Style().configure(STYLE, background=colour)


class _ActionItemSection(Frame):
    def __init__(
        self,
        parent: Misc,
        initial_message: str,
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
        self.columnconfigure(index=0, weight=1)
        self._message = ResponsiveTextbox(
            self,
            width=50,
            font=normal_font,
            background=background,
            foreground=foreground,
            pady=25,
        )
        self._message.grid(row=0, column=0, sticky="NEW")
        self._message.set_text(initial_message)
        self._grid = _ActionItemGrid(
            self,
            padx=padx,
            pady=pady,
            background=background,
            foreground=foreground,
            normal_font=normal_font,
            header_font=header_font,
        )

    def add_row(
        self,
        index: Optional[int],
        task_name: str,
        message: str,
        on_click_done: Optional[Callable[[], None]],
        on_click_retry: Optional[Callable[[], None]],
        on_click_skip: Optional[Callable[[], None]],
    ) -> int:
        num_rows_before = self._grid.num_rows
        index = self._grid.add_row(
            index=index,
            task_name=task_name,
            message=message,
            on_click_done=on_click_done,
            on_click_retry=on_click_retry,
            on_click_skip=on_click_skip,
        )
        if num_rows_before == 0 and self._grid.num_rows > 0:
            self._message.grid_forget()
            self._grid.grid(row=0, column=0, sticky="NEW")
        return index

    def delete_row(self, index: int) -> None:
        self._grid.delete_row(index)
        if self._grid.num_rows == 0:
            self._grid.grid_forget()
            self._message.grid(row=0, column=0, sticky="NEW")

    def set_message(self, message: str) -> None:
        self._message.set_text(message)


class _ActionItemGrid(Frame):
    _DONE_BTN_COLUMN = 0
    _DONE_BTN_WIDTH = 7
    _RETRY_BTN_COLUMN = 1
    _RETRY_BTN_WIDTH = 7
    _SKIP_BTN_COLUMN = 2
    _SKIP_BTN_WIDTH = 7
    _NAME_COLUMN = 3
    _NAME_WIDTH = 35
    _MSG_COLUMN = 4
    _MSG_WIDTH = 108

    def __init__(
        self,
        parent: Misc,
        padx: int,
        pady: int,
        background: str,
        foreground: str,
        normal_font: str,
        header_font: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(parent, *args, **kwargs)

        self._padx = padx
        self._pady = pady
        self._background = background
        self._foreground = foreground
        self._normal_font = normal_font
        self._header_font = header_font

        self.columnconfigure(index=self._NAME_COLUMN, weight=1)
        self.columnconfigure(index=self._MSG_COLUMN, weight=4)

        self._widgets: Dict[
            int,
            Tuple[
                Optional[Button],
                Optional[Button],
                Optional[Button],
                ResponsiveTextbox,
                ResponsiveTextbox,
            ],
        ] = {}
        self._create_header()

    def add_row(
        self,
        index: Optional[int],
        task_name: str,
        message: str,
        on_click_done: Optional[Callable[[], None]],
        on_click_retry: Optional[Callable[[], None]],
        on_click_skip: Optional[Callable[[], None]],
    ) -> int:
        if index is None or index in self._widgets:
            # If the index is the same as an existing row, tkinter seems to
            # overwrite the existing widgets. It's better to avoid that and
            # just put this action item at the buttom.
            actual_index = max(self._widgets.keys()) + 1 if self._widgets else 0
        else:
            actual_index = index

        if on_click_done is not None:
            done_button = Button(
                self, text="Done", state="enabled", width=self._DONE_BTN_WIDTH
            )
            done_button.configure(command=on_click_done)
            done_button.grid(
                # Increase the row number to account for the header
                row=actual_index + 2,
                column=self._DONE_BTN_COLUMN,
                padx=self._padx,
                pady=self._pady,
                sticky="NEW",
            )
        else:
            done_button = None
        if on_click_retry is not None:
            retry_button = Button(self, text="Retry", width=self._RETRY_BTN_WIDTH)
            retry_button.configure(command=on_click_retry)
            retry_button.grid(
                row=actual_index + 2,
                column=self._RETRY_BTN_COLUMN,
                padx=self._padx,
                pady=self._pady,
                sticky="NEW",
            )
        else:
            retry_button = None
        if on_click_skip is not None:
            skip_button = Button(self, text="Skip", width=self._SKIP_BTN_WIDTH)
            skip_button.configure(command=on_click_skip)
            skip_button.grid(
                row=actual_index + 2,
                column=self._SKIP_BTN_COLUMN,
                padx=self._padx,
                pady=self._pady,
                sticky="NEW",
            )
        else:
            skip_button = None
        name_label = ResponsiveTextbox(
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
            sticky="NEW",
        )
        name_label.set_text(_friendly_name(task_name))
        msg_label = ResponsiveTextbox(
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
            sticky="NEW",
        )
        msg_label.set_text(message)

        self._widgets[actual_index] = (
            done_button,
            retry_button,
            skip_button,
            name_label,
            msg_label,
        )

        return actual_index

    def delete_row(self, index: int):
        if index not in self._widgets:
            return
        (done_btn, retry_btn, skip_btn, name_label, msg_label) = self._widgets[index]
        del self._widgets[index]
        if done_btn is not None:
            done_btn.destroy()
        if retry_btn is not None:
            retry_btn.destroy()
        if skip_btn is not None:
            skip_btn.destroy()
        name_label.destroy()
        msg_label.destroy()

    @property
    def num_rows(self) -> int:
        return len(self._widgets)

    def _create_header(self):
        # Include the empty header cells for the buttons just to keep the UI
        # stable whether or not the grid has entries
        done_button_header_label = ResponsiveTextbox(
            self,
            width=self._DONE_BTN_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        done_button_header_label.grid(
            row=0,
            column=self._DONE_BTN_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )

        retry_button_header_label = ResponsiveTextbox(
            self,
            width=self._RETRY_BTN_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        retry_button_header_label.grid(
            row=0,
            column=self._RETRY_BTN_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )

        skip_button_header_label = ResponsiveTextbox(
            self,
            width=self._SKIP_BTN_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        skip_button_header_label.grid(
            row=0,
            column=self._SKIP_BTN_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )

        name_header_label = ResponsiveTextbox(
            self,
            width=self._NAME_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_header_label.grid(
            row=0,
            column=self._NAME_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        name_header_label.set_text("Task")

        msg_header_label = ResponsiveTextbox(
            self,
            width=self._MSG_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        msg_header_label.grid(
            row=0,
            column=self._MSG_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        msg_header_label.set_text("Instructions")

        separator = _ThickSeparator(
            self, thickness=3, orient="horizontal", colour=self._foreground
        )
        separator.grid(row=1, column=0, columnspan=5, sticky="EW")


class _TaskStatusGrid(Frame):
    _COMMANDS_COLUMN = 0
    _COMMANDS_WIDTH = 10
    _STATUS_COLUMN = 1
    _STATUS_WIDTH = 20
    _NAME_COLUMN = 2
    _NAME_WIDTH = 35
    _MSG_COLUMN = 3
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

        self.columnconfigure(index=self._NAME_COLUMN, weight=1)
        self.columnconfigure(index=self._MSG_COLUMN, weight=4)

        self._taken_indices: Set[int] = set()
        self._widgets_by_name: Dict[
            str, Tuple[Frame, ResponsiveTextbox, ResponsiveTextbox]
        ] = {}
        self._command: Dict[Tuple[str, str], Button] = {}
        self._create_header()

    def upsert_row(
        self, index: Optional[int], task_name: str, status: TaskStatus, message: str
    ):
        if task_name in self._widgets_by_name:
            # Update existing row
            (_, status_label, msg_label) = self._widgets_by_name[task_name]
        else:
            # Add new row
            if index is None or index in self._taken_indices:
                actual_index = (
                    max(self._taken_indices) + 1 if self._taken_indices else 0
                )
            else:
                actual_index = index

            commands_frame = Frame(self, width=self._COMMANDS_WIDTH)
            commands_frame.grid(
                # Increase the row number to account for the header
                row=actual_index + 2,
                column=self._COMMANDS_COLUMN,
                padx=self._padx,
                pady=self._pady,
                sticky="NEW",
            )
            name_label = ResponsiveTextbox(
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
                sticky="NEW",
            )
            name_label.set_text(_friendly_name(task_name))
            status_label = ResponsiveTextbox(
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
                sticky="NEW",
            )
            msg_label = ResponsiveTextbox(
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
                sticky="NEW",
            )
            self._taken_indices.add(actual_index)
            self._widgets_by_name[task_name] = (commands_frame, status_label, msg_label)

        status_label.set_text(_friendly_status(status))
        status_label.config(foreground=_status_colour(status))
        msg_label.set_text(message)

    def upsert_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ):
        if task_name not in self._widgets_by_name:
            self.upsert_row(
                index=None,
                task_name=task_name,
                status=TaskStatus.RUNNING,
                message="This task is cancellable.",
            )
        (commands_frame, _, _) = self._widgets_by_name[task_name]
        if (task_name, command_name) in self._command:
            existing_button = self._command[(task_name, command_name)]
            existing_button.config(command=callback)
        else:
            button = Button(commands_frame, text=command_name, command=callback)
            button.pack()
            self._command[(task_name, command_name)] = button

    def remove_command(self, task_name: str, command_name: str):
        if (task_name, command_name) in self._command:
            existing_button = self._command[(task_name, command_name)]
            del self._command[(task_name, command_name)]
            existing_button.destroy()

    def _create_header(self):
        command_header_label = ResponsiveTextbox(
            self,
            width=self._COMMANDS_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        command_header_label.grid(
            row=0,
            column=self._COMMANDS_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        command_header_label.set_text("")

        name_header_label = ResponsiveTextbox(
            self,
            width=self._NAME_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_header_label.grid(
            row=0,
            column=self._NAME_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        name_header_label.set_text("Task")

        status_header_label = ResponsiveTextbox(
            self,
            width=self._STATUS_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        status_header_label.grid(
            row=0,
            column=self._STATUS_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        status_header_label.set_text("Status")

        msg_header_label = ResponsiveTextbox(
            self,
            width=self._MSG_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        msg_header_label.grid(
            row=0,
            column=self._MSG_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        msg_header_label.set_text("Details")

        separator = _ThickSeparator(
            self, thickness=3, orient="horizontal", colour=self._foreground
        )
        separator.grid(row=1, column=0, columnspan=4, sticky="EW")


class _ProblemGrid(Frame):
    _NAME_COLUMN = 1
    _NAME_WIDTH = 35
    _LEVEL_COLUMN = 0
    _LEVEL_WIDTH = 10
    _MSG_COLUMN = 2
    _MSG_WIDTH = 110

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

        self.columnconfigure(index=self._NAME_COLUMN, weight=1)
        self.columnconfigure(index=self._MSG_COLUMN, weight=4)

        self._current_row = 0
        self._create_header()

    def add_row(self, task_name: str, level: ProblemLevel, message: str):
        name_label = ResponsiveTextbox(
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
            sticky="NEW",
        )
        name_label.set_text(_friendly_name(task_name))

        level_label = ResponsiveTextbox(
            self,
            width=self._LEVEL_WIDTH,
            foreground=_level_colour(level),
            font=self._bold_font,
            background=self._background,
        )
        level_label.grid(
            row=self._current_row + 2,
            column=self._LEVEL_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        level_label.set_text(str(level))

        self._message_label = ResponsiveTextbox(
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
            sticky="NEW",
        )
        self._message_label.set_text(message)

        self._current_row += 1

    def _create_header(self):
        name_header_label = ResponsiveTextbox(
            self,
            width=self._NAME_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        name_header_label.grid(
            row=0,
            column=self._NAME_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        name_header_label.set_text("Task")

        level_header_label = ResponsiveTextbox(
            self,
            width=self._LEVEL_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        level_header_label.grid(
            row=0,
            column=self._LEVEL_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        level_header_label.set_text("Level")

        msg_header_label = ResponsiveTextbox(
            self,
            width=self._MSG_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        msg_header_label.grid(
            row=0,
            column=self._MSG_COLUMN,
            padx=self._padx,
            pady=self._pady,
            sticky="NEW",
        )
        msg_header_label.set_text("Details")

        separator = _ThickSeparator(
            self, thickness=3, orient="horizontal", colour=self._foreground
        )
        separator.grid(row=1, column=0, columnspan=3, sticky="EW")


class InputCancelledException(Exception):
    pass


def _position_toplevel(tk: Tk, w: Toplevel) -> None:
    tk.update_idletasks()
    x = tk.winfo_x()
    y = tk.winfo_y()
    w.geometry(f"+{x}+{y}")


def _friendly_name(name: str) -> str:
    # Shouldn't normally happen
    if len(name) == 0:
        return name
    s = name.replace("_", " ")
    capitalized = s[0].upper() + s[1:]
    return capitalized


def _friendly_status(status: TaskStatus) -> str:
    return str(status).replace("_", " ")


def _status_colour(status: TaskStatus) -> str:
    if status == TaskStatus.NOT_STARTED:
        return "#888888"
    elif status == TaskStatus.RUNNING:
        return "#ADD8E6"
    elif status == TaskStatus.WAITING_FOR_USER:
        return "#FF7700"
    elif status == TaskStatus.DONE:
        return "#009020"
    elif status == TaskStatus.SKIPPED:
        return "#FF0000"
    else:
        return "#000000"


def _level_colour(level: ProblemLevel) -> str:
    if level == ProblemLevel.WARN:
        return "#FF7700"
    elif level == ProblemLevel.ERROR:
        return "#FF0000"
    elif level == ProblemLevel.FATAL:
        return "#990000"
    else:
        return "#000000"
