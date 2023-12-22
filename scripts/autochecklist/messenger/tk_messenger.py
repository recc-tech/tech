# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import ctypes
import subprocess
import threading
import tkinter
import typing
from argparse import ArgumentTypeError
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Lock
from tkinter import Canvas, Menu, Misc, Text, Tk, Toplevel, messagebox
from tkinter.ttk import Button, Entry, Frame, Label, Scrollbar, Style
from typing import Any, Callable, Dict, Literal, Optional, Set, Tuple, TypeVar

import pyperclip

from .input_messenger import (
    InputMessenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
    UserResponse,
)

T = TypeVar("T")


_BACKGROUND_COLOUR = "#EEEEEE"
_FOREGROUND_COLOUR = "#000000"

_NORMAL_FONT = "Calibri 12"
_ITALIC_FONT = f"{_NORMAL_FONT} italic"
_BOLD_FONT = f"{_NORMAL_FONT} bold"
_H2_FONT = "Calibri 18 bold"


# TODO: This hangs when the user tries to cancel while a long-running task is
# still going.
class TkMessenger(InputMessenger):
    _QUEUE_EVENT = "<<TaskQueued>>"

    def __init__(self, title: str, description: str) -> None:
        self._title = title
        self._description = description
        self._start_event = threading.Event()
        self._end_event = threading.Event()
        self._mutex = Lock()
        self._waiting_events: Set[threading.Event] = set()
        self._queue: Queue[_GuiTask] = Queue()

    def run_main_loop(self) -> None:
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
            print(f"Exception in custom event handler: {e}")

    def wait_for_start(self) -> None:
        self._start_event.wait()

    @property
    def is_closed(self) -> bool:
        return self._end_event.is_set()

    def close(self) -> None:
        def show_goodbye_message() -> None:
            self._action_items_grid.destroy()
            goodbye_textbox = _CopyableText(
                self._action_items_frame,
                width=170,
                height=0,
                font=_NORMAL_FONT,
                background=_BACKGROUND_COLOUR,
                foreground=_FOREGROUND_COLOUR,
            )
            goodbye_textbox.grid(sticky="NW", pady=25)
            goodbye_textbox.set_text("The program is done. Close this window to exit.")

        if self.is_closed:
            return
        else:
            self._tk.after_idle(show_goodbye_message)
            self._end_event.wait()

    def log_status(
        self, task_name: str, index: Optional[int], status: TaskStatus, message: str
    ) -> None:
        if self.is_closed:
            raise KeyboardInterrupt()

        def do_log_status() -> None:
            self._task_statuses_grid.upsert_row(
                index=index, task_name=task_name, status=status, message=message
            )

        self._queue.put(_GuiTask(do_log_status, update_scrollregion=True))
        self._tk.event_generate(self._QUEUE_EVENT)

    def log_problem(self, task_name: str, level: ProblemLevel, message: str) -> None:
        if self.is_closed:
            raise KeyboardInterrupt()

        def do_log_problem() -> None:
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
        param = Parameter(display_name, parser, password, description=prompt)
        results = self.input_multiple({"param": param}, prompt="", title=title)
        return typing.cast(T, results["param"])

    def input_multiple(
        self, params: Dict[str, Parameter], prompt: str = "", title: str = ""
    ) -> Dict[str, object]:
        def handle_submit() -> None:
            submit_event.set()

        def handle_close() -> None:
            nonlocal was_input_cancelled
            # IMPORTANT: If this is changed to call another method with a
            # custom boolean input dialog, it MUST NOT deadlock the main thread
            # (e.g., by generating an event but then blocking on main).
            should_exit = messagebox.askyesno(
                title="Confirm exit",
                message="Are you sure you want to close the input dialog? This will interrupt whatever task was expecting input.",
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
        error_label_by_key: Dict[str, _CopyableText]
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
        return messagebox.askyesno(title, prompt)

    def wait(
        self, task_name: str, index: Optional[int], prompt: str, allow_retry: bool
    ) -> UserResponse:
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

        def do_add_action_item() -> None:
            nonlocal actual_index
            actual_index = self._action_items_grid.add_row(
                index,
                task_name,
                prompt,
                on_click_done=handle_click_done,
                on_click_retry=handle_click_retry if allow_retry else None,
            )

        def do_remove_action_item() -> None:
            self._action_items_grid.delete_row(actual_index)

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
        def do_add_command() -> None:
            self._task_statuses_grid.upsert_command(task_name, command_name, callback)

        self._queue.put(_GuiTask(do_add_command, update_scrollregion=False))
        self._tk.event_generate(self._QUEUE_EVENT)

    def remove_command(self, task_name: str, command_name: str) -> None:
        def do_remove_command() -> None:
            self._task_statuses_grid.remove_command(task_name, command_name)

        self._queue.put(_GuiTask(do_remove_command, update_scrollregion=False))
        self._tk.event_generate(self._QUEUE_EVENT)

    def _handle_update_scrollregion(self) -> None:
        # Make sure the display has updated before recomputing the scrollregion size
        self._tk.update_idletasks()
        canvas = typing.cast(Canvas, self._scroll_frame.master)
        region = canvas.bbox("all")
        canvas.config(scrollregion=region)

    def _confirm_exit(self):
        should_exit = self.input_bool(
            title="Confirm exit", prompt="Are you sure you want to exit?"
        )
        if should_exit:
            self._tk.quit()

    def _create_gui(self) -> None:
        # Try to make the GUI less blurry
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self._tk = Tk()
        self._tk.title(self._title)
        screen_height = self._tk.winfo_screenheight()
        # Apparently tk.winfo_screenwidth() doesn't work very well on
        # multi-monitor setups
        approx_screen_width = 16 * screen_height / 9
        window_width = int(approx_screen_width * 0.75)
        window_height = int(screen_height * 0.75)
        self._tk.geometry(f"{window_width}x{window_height}+0+0")
        self._scroll_frame = _create_scrollable_frame(
            self._tk, self._handle_update_scrollregion, padding=25
        )
        # For some reason, `self._scroll_frame.pack(fill="both", expand=1)`
        # causes canvas.bbox("all") to always return (0, 0, 1, 1)

        # -------------------- Behaviour --------------------

        self._tk.protocol("WM_DELETE_WINDOW", self._confirm_exit)
        self._right_click_menu = self._create_right_click_menu()
        self._tk.bind_all(sequence="<Button-3>", func=self._show_right_click_menu)
        self._tk.bind_all(self._QUEUE_EVENT, func=lambda _: self._handle_queued_task())

        # -------------------- Style --------------------

        self._tk.config(background=_BACKGROUND_COLOUR)
        style = Style()
        style.configure(
            "TButton",
            font=_NORMAL_FONT,
        )
        style.configure(
            "TFrame",
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
        )

        WIDTH = 170

        # -------------------- Description --------------------

        # TODO: Fixed-width text boxes kind of suck. What if I set an explicit
        # width right before counting lines and then restored to sticky mode
        # after?
        if self._description.strip():
            description_textbox = _CopyableText(
                self._scroll_frame,
                width=WIDTH,
                font=_ITALIC_FONT,
                background=_BACKGROUND_COLOUR,
                foreground=_FOREGROUND_COLOUR,
            )
            description_textbox.grid(sticky="NW", pady=25)
            description_textbox.set_text(self._description)

        # -------------------- Action items section --------------------

        self._action_items_frame = Frame(self._scroll_frame)
        self._action_items_frame.grid(sticky="NEW")

        action_items_header = _CopyableText(
            self._action_items_frame,
            width=WIDTH,
            font=_H2_FONT,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
        )
        action_items_header.grid(sticky="NW", pady=(50, 0))
        action_items_header.set_text("Action Items")

        action_items_description = _CopyableText(
            self._action_items_frame,
            width=WIDTH,
            font=_ITALIC_FONT,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
        )
        action_items_description.grid(sticky="NW", pady=25)
        action_items_description.set_text(
            "Tasks that you must perform manually are listed here."
        )

        self._action_items_grid = _ActionItemGrid(
            self._action_items_frame,
            outer_padding=5,
            padx=5,
            pady=5,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
            normal_font=_NORMAL_FONT,
            header_font=_BOLD_FONT,
        )
        self._action_items_grid.grid(sticky="NEW")

        # -------------------- Task statuses section --------------------

        task_statuses_header = _CopyableText(
            self._scroll_frame,
            width=WIDTH,
            font=_H2_FONT,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
        )
        task_statuses_header.grid(sticky="NEW", pady=(50, 0))
        task_statuses_header.set_text("Task Statuses")

        task_statuses_description = _CopyableText(
            self._scroll_frame,
            width=WIDTH,
            font=_ITALIC_FONT,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
        )
        task_statuses_description.grid(sticky="NEW", pady=25)
        task_statuses_description.set_text("The status of each task is listed here.")

        self._task_statuses_grid = _TaskStatusGrid(
            self._scroll_frame,
            outer_padding=5,
            padx=5,
            pady=5,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
            normal_font=_NORMAL_FONT,
            header_font=_BOLD_FONT,
            bold_font=_BOLD_FONT,
        )
        self._task_statuses_grid.grid(sticky="NEW")

        # -------------------- Problems section --------------------

        problems_header = _CopyableText(
            self._scroll_frame,
            width=WIDTH,
            font=_H2_FONT,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
        )
        problems_header.grid(sticky="NEW", pady=(50, 0))
        problems_header.set_text("Problems")

        problems_description = _CopyableText(
            self._scroll_frame,
            width=WIDTH,
            font=_ITALIC_FONT,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
        )
        problems_description.grid(sticky="NEW", pady=25)
        problems_description.set_text("Potential problems are listed here.")

        self._problems_grid = _ProblemGrid(
            self._scroll_frame,
            outer_padding=5,
            padx=5,
            pady=5,
            background=_BACKGROUND_COLOUR,
            foreground=_FOREGROUND_COLOUR,
            normal_font=_NORMAL_FONT,
            header_font=_BOLD_FONT,
            bold_font=_BOLD_FONT,
        )
        self._problems_grid.grid(sticky="NEW")

    def _create_input_dialog(
        self, title: str, prompt: str, params: Dict[str, Parameter]
    ) -> Tuple[Toplevel, Dict[str, Entry], Dict[str, _CopyableText], Button]:
        entry_by_name: Dict[str, Entry] = {}
        error_message_by_name: Dict[str, _CopyableText] = {}
        w = Toplevel(self._tk, padx=10, pady=10, background=_BACKGROUND_COLOUR)
        try:
            w.title(title)
            if prompt:
                prompt_box = Label(
                    w, text=prompt, font=_ITALIC_FONT, padding=(0, 0, 0, 50)
                )
                prompt_box.grid()
            for name, param in params.items():
                param_frame = Frame(w)
                param_frame.grid(pady=15)
                entry_row = Frame(param_frame)
                entry_row.grid()
                name_label = Label(entry_row, text=param.display_name, font=_BOLD_FONT)
                name_label.grid(row=0, column=0, padx=5)
                if param.password:
                    entry = Entry(entry_row, show="*", font=_NORMAL_FONT)
                else:
                    entry = Entry(entry_row, font=_NORMAL_FONT)
                entry.grid(row=0, column=1, padx=5)
                if param.default:
                    entry.insert(0, param.default)
                entry_by_name[name] = entry
                if param.description:
                    description_box = _CopyableText(
                        param_frame,
                        font=_ITALIC_FONT,
                        background=_BACKGROUND_COLOUR,
                        foreground=_FOREGROUND_COLOUR,
                    )
                    description_box.grid()
                    description_box.set_text(param.description)
                error_message = _CopyableText(
                    param_frame,
                    font=_NORMAL_FONT,
                    background=_BACKGROUND_COLOUR,
                    foreground="red",
                )
                error_message.grid()
                error_message_by_name[name] = error_message
            btn = Button(w, text="Done")
            btn.grid()
            return (w, entry_by_name, error_message_by_name, btn)
        except:
            w.destroy()
            raise

    def _create_right_click_menu(self) -> Menu:
        menu = Menu(None, tearoff=0)
        menu.add_command(label="Copy", command=self._right_click_copy)
        menu.add_command(
            label="Open in Notepad++", command=self._right_click_open_in_notepadpp
        )
        # TODO: Add more menu options
        # menu.add_command(label="Cut")
        # menu.add_command(label="Paste", command=pyperclip.paste)
        # menu.add_command(label="Open in browser")
        return menu

    def _show_right_click_menu(self, event: tkinter.Event[Misc]):
        self._right_click_menu.entryconfig(
            "Copy",
            state="normal" if self._get_selected_text() else "disabled",
        )
        self._right_click_menu.entryconfig(
            "Open in Notepad++",
            state="normal" if self._is_selected_text_a_filename() else "disabled",
        )
        self._right_click_menu.tk_popup(x=event.x_root, y=event.y_root)

    def _right_click_copy(self):
        try:
            text = self._get_selected_text()
            if not text:
                return
            pyperclip.copy(text)
        except Exception as e:
            print(e)
            messagebox.showwarning(
                title="Failed to copy",
                message="An error occurred. Please try again.",
            )

    def _is_selected_text_a_filename(self) -> bool:
        try:
            text = self._get_selected_text()
            if not text:
                return False
            path = Path(text)
            return path.is_file()
        except Exception:
            return False

    def _right_click_open_in_notepadpp(self):
        try:
            text = self._get_selected_text()
            if not text:
                return
            path = Path(text)
            if path.is_file():
                subprocess.run(f'notepad++.exe "{path.as_posix()}"')
        except Exception:
            messagebox.showwarning(
                title="Failed to open in Notepad++",
                message="An error occurred. Please try again.",
            )

    def _get_selected_text(self) -> str:
        try:
            # TODO: the selection doesn't get cleared when you click from one
            # text box to another :( If you click elsewhere, selection_get
            # still returns the previously-selected text.
            text = str(self._tk.selection_get())
            return text
        except Exception:
            return ""

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


def _create_scrollable_frame(
    tk: Tk, update_scrollregion: Callable[[], None], padding: int
) -> Frame:
    outer_frame = Frame(tk)
    outer_frame.pack(fill="both", expand=1)

    scrollbar = Scrollbar(outer_frame, orient="vertical")
    scrollbar.pack(side="right", fill="y")
    canvas = Canvas(
        outer_frame,
        yscrollcommand=scrollbar.set,
        borderwidth=0,
        highlightthickness=0,
    )
    canvas.pack(side="left", fill="both", expand=1)
    canvas.bind("<Configure>", lambda e: update_scrollregion())
    scrollbar.config(command=canvas.yview)

    # Allow scrolling with the mouse (why does this not work out of the box? D:<<)
    tk.bind_all(
        "<MouseWheel>",
        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
    )

    frame = Frame(canvas, padding=padding)
    canvas.create_window((0, 0), window=frame, anchor="nw")
    return frame


class _CopyableText(Text):
    """
    Text widget that supports both text wrapping and copying its contents to the clipboard.
    """

    def __init__(self, parent: Misc, **kwargs: Any):
        kwargs["height"] = 1
        kwargs["wrap"] = "word"
        kwargs["state"] = "disabled"
        kwargs["highlightthickness"] = 0
        kwargs["borderwidth"] = 0
        super().__init__(parent, **kwargs)

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
        Style().configure(STYLE, background=colour)


class _ActionItemGrid(Frame):
    _DONE_BTN_COLUMN = 0
    _DONE_BTN_WIDTH = 7
    _RETRY_BTN_COLUMN = 1
    _RETRY_BTN_WIDTH = 7
    _NAME_COLUMN = 2
    _NAME_WIDTH = 35
    _MSG_COLUMN = 3
    _MSG_WIDTH = 115

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

        self._widgets: Dict[
            int, Tuple[Button, Optional[Button], _CopyableText, _CopyableText]
        ] = {}
        self._create_header()

    def add_row(
        self,
        index: Optional[int],
        task_name: str,
        message: str,
        on_click_done: Callable[[], None],
        on_click_retry: Optional[Callable[[], None]],
    ) -> int:
        if index is None or index in self._widgets:
            # If the index is the same as an existing row, tkinter seems to
            # overwrite the existing widgets. It's better to avoid that and
            # just put this action item at the buttom.
            actual_index = max(self._widgets.keys()) + 1 if self._widgets else 0
        else:
            actual_index = index

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
        )
        if on_click_retry is not None:
            retry_button = Button(
                self, text="Retry", state="enabled", width=self._RETRY_BTN_WIDTH
            )
            retry_button.configure(command=on_click_retry)
            retry_button.grid(
                row=actual_index + 2,
                column=self._RETRY_BTN_COLUMN,
                padx=self._padx,
                pady=self._pady,
            )
        else:
            retry_button = None
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

        self._widgets[actual_index] = (done_button, retry_button, name_label, msg_label)

        return actual_index

    def delete_row(self, index: int):
        if index not in self._widgets:
            return
        (done_button, retry_button, name_label, msg_label) = self._widgets[index]
        del self._widgets[index]
        done_button.destroy()
        if retry_button is not None:
            retry_button.destroy()
        name_label.destroy()
        msg_label.destroy()

    def _create_header(self):
        # Include the empty header cells for the buttons just to keep the UI
        # stable whether or not the grid has entries
        done_button_header_label = _CopyableText(
            self,
            width=self._DONE_BTN_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        done_button_header_label.grid(
            row=0, column=self._DONE_BTN_COLUMN, padx=self._padx, pady=self._pady
        )

        retry_button_header_label = _CopyableText(
            self,
            width=self._RETRY_BTN_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        retry_button_header_label.grid(
            row=0, column=self._RETRY_BTN_COLUMN, padx=self._padx, pady=self._pady
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
        separator.grid(row=1, column=0, columnspan=4, sticky="EW")


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

        self._taken_indices: Set[int] = set()
        self._widgets_by_name: Dict[
            str, Tuple[Frame, _CopyableText, _CopyableText]
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
            self._taken_indices.add(actual_index)
            self._widgets_by_name[task_name] = (commands_frame, status_label, msg_label)

        status_label.set_text(str(status))
        status_label.config(foreground=self._status_colour(status))
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
        command_header_label = _CopyableText(
            self,
            width=self._COMMANDS_WIDTH,
            font=self._header_font,
            background=self._background,
            foreground=self._foreground,
        )
        command_header_label.grid(
            row=0, column=self._COMMANDS_COLUMN, padx=self._padx, pady=self._pady
        )
        command_header_label.set_text("")

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
        separator.grid(row=1, column=0, columnspan=4, sticky="EW")

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


class InputCancelledException(Exception):
    pass
