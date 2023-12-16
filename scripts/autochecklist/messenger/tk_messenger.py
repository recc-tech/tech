from __future__ import annotations

import ctypes
import subprocess
import threading
import tkinter as tk
from argparse import ArgumentTypeError
from pathlib import Path
from threading import Event, Lock, Semaphore, Thread
from tkinter import Canvas, Menu, Misc, Text, Tk, Toplevel, messagebox
from tkinter.ttk import Button, Entry, Frame, Label, Scrollbar, Style
from typing import Callable, Dict, Literal, Optional, Set, Tuple, TypeVar, cast

import pyperclip  # type: ignore
from autochecklist.messenger.input_messenger import (
    InputMessenger,
    Parameter,
    ProblemLevel,
    TaskStatus,
    UserResponse,
    interrupt_main_thread,
    is_current_thread_main,
)

T = TypeVar("T")


class TkMessenger(InputMessenger):
    _BACKGROUND_COLOUR = "#EEEEEE"
    _FOREGROUND_COLOUR = "#000000"

    _NORMAL_FONT = "Calibri 12"
    _ITALIC_FONT = f"{_NORMAL_FONT} italic"
    _BOLD_FONT = f"{_NORMAL_FONT} bold"
    _H2_FONT = "Calibri 18 bold"

    def __init__(self, title: str, description: str):
        self._mutex = Lock()
        self._close_called = False
        self._is_main_thread_waiting_for_input = False
        self._is_shut_down = False
        self._waiting_locks: Set[Lock] = set()
        self._waiting_events: Set[Event] = set()
        root_started = Semaphore(0)
        self._gui_thread = Thread(
            name="TkMessenger",
            target=lambda: self._run_gui(title, root_started, description),
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
    ) -> T:
        # simpledialog.askstring throws an exception each time :(
        # https://stackoverflow.com/questions/53480400/tkinter-askstring-deleted-before-its-visibility-changed
        param = Parameter(display_name, parser, password, description=prompt)
        results = self.input_multiple({"param": param}, prompt="", title=title)
        return cast(T, results["param"])

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
            if is_current_thread_main():
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
                if is_current_thread_main():
                    self._is_main_thread_waiting_for_input = False
                # If quit() was already called then the entire GUI is already
                # being destroyed. If this call to destroy() happens after the
                # GUI mainloop exits, then this code will deadlock.
                if not self._is_shut_down:
                    w.destroy()

    def input_bool(self, prompt: str, title: str = "") -> bool:
        return messagebox.askyesno(title, prompt)  # type: ignore

    def wait(
        self, task_name: str, index: Optional[int], prompt: str, allow_retry: bool
    ) -> UserResponse:
        response: Optional[UserResponse] = None
        event = Event()

        def handle_done_click():
            nonlocal response, event
            # Keep the first choice if the user somehow presses both quickly
            response = response or UserResponse.DONE
            event.set()

        def handle_retry_click():
            nonlocal response, event
            response = response or UserResponse.RETRY
            event.set()

        with self._mutex:
            self._waiting_events.add(event)
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            actual_index = self._action_items_grid.add_row(
                index,
                task_name=task_name,
                message=prompt,
                on_click_done=handle_done_click,
                on_click_retry=(handle_retry_click if allow_retry else None),
            )
            self._root_frame.update_scrollregion()
        event.wait()
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            self._waiting_events.remove(event)
            self._action_items_grid.delete_row(actual_index)
            # Update the scrollregion again in case it got smaller
            self._root_frame.update_scrollregion()
        # Response should always be set here because the button click handlers
        # set it, but set a default just in case. Default to DONE rather than
        # RETRY so the script doesn't get stuck in an infinite loop
        return response or UserResponse.DONE

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

    @property
    def is_closed(self) -> bool:
        with self._mutex:
            return self._is_shut_down

    def add_command(
        self, task_name: str, command_name: str, callback: Callable[[], None]
    ) -> None:
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            self._task_statuses_grid.upsert_command(
                task_name=task_name,
                command_name=command_name,
                callback=callback,
            )
            self._root_frame.update_scrollregion()

    def remove_command(self, task_name: str, command_name: str) -> None:
        with self._mutex:
            if self._is_shut_down:
                raise KeyboardInterrupt()
            self._task_statuses_grid.remove_command(
                task_name=task_name, command_name=command_name
            )
            self._root_frame.update_scrollregion()

    def _run_gui(self, title: str, root_started: Semaphore, description: str):
        # Try to make the GUI less blurry
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

        self._tk = Tk()
        self._tk.title(title)
        self._tk.protocol("WM_DELETE_WINDOW", self._confirm_exit)
        self._tk.config(background=self._BACKGROUND_COLOUR)
        self._tk.bind_all(sequence="<Button-3>", func=self._show_right_click_menu)

        screen_height = self._tk.winfo_screenheight()
        approx_screen_width = 16 * screen_height / 9
        window_width = int(approx_screen_width * 0.75)
        window_height = (screen_height * 3) // 4
        self._tk.geometry(f"{window_width}x{window_height}")

        self._root_frame = _ScrollableFrame(self._tk)

        self._right_click_menu = self._create_right_click_menu()

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

    def _show_right_click_menu(self, event: tk.Event[Misc]):
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
            pyperclip.copy(text)  # type: ignore
        except Exception:
            messagebox.showwarning(  # type: ignore
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
        except:
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
            messagebox.showwarning(  # type: ignore
                title="Failed to open in Notepad++",
                message="An error occurred. Please try again.",
            )

    def _get_selected_text(self) -> str:
        try:
            # TODO: the selection doesn't get cleared when you click from one
            # text box to another :( If you click elsewhere, selection_get
            # still returns the previously-selected text.
            text = str(self._tk.selection_get())  # type: ignore
            return text
        except Exception:
            return ""

    def _create_input_window(
        self, title: str, prompt: str, params: Dict[str, Parameter]
    ) -> Tuple[Toplevel, Dict[str, Entry], Dict[str, _CopyableText], Button]:
        entry_by_name: Dict[str, Entry] = {}
        error_message_by_name: Dict[str, _CopyableText] = {}
        w = Toplevel(self._tk, padx=10, pady=10, background=self._BACKGROUND_COLOUR)
        try:
            w.title(title)
            if prompt:
                prompt_box = Label(
                    w, text=prompt, font=self._ITALIC_FONT, padding=(0, 0, 0, 50)
                )
                prompt_box.grid()
            for name, param in params.items():
                param_frame = Frame(w)
                param_frame.grid(pady=15)
                entry_row = Frame(param_frame)
                entry_row.grid()
                name_label = Label(
                    entry_row, text=param.display_name, font=self._BOLD_FONT
                )
                name_label.grid(row=0, column=0, padx=5)
                if param.password:
                    entry = Entry(entry_row, show="*", font=self._NORMAL_FONT)
                else:
                    entry = Entry(entry_row, font=self._NORMAL_FONT)
                entry.grid(row=0, column=1, padx=5)
                if param.default:
                    entry.insert(0, param.default)
                entry_by_name[name] = entry
                if param.description:
                    description_box = _CopyableText(
                        param_frame,
                        font=self._ITALIC_FONT,
                        background=self._BACKGROUND_COLOUR,
                        foreground=self._FOREGROUND_COLOUR,
                    )
                    description_box.grid()
                    description_box.set_text(param.description)
                error_message = _CopyableText(
                    param_frame,
                    font=self._NORMAL_FONT,
                    background=self._BACKGROUND_COLOUR,
                    foreground="red",
                )
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
                if (
                    not self._close_called
                    and not self._is_main_thread_waiting_for_input
                ):
                    interrupt_main_thread()
            self._quit()

    def _quit(self):
        with self._mutex:
            # If the GUI thread isn't alive, then probably _quit() was already
            # called
            if self._is_shut_down:
                return
            self._is_shut_down = True
            for lock in self._waiting_locks:
                if lock.locked():
                    lock.release()
            for event in self._waiting_events:
                event.set()
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
        self._update_scrollregion = threading.Event()
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

    def __init__(self, parent: Misc, **kwargs: object):
        super().__init__(
            parent,
            height=1,
            wrap="word",
            state="disabled",
            highlightthickness=0,
            borderwidth=0,
            **kwargs,  # type: ignore
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
