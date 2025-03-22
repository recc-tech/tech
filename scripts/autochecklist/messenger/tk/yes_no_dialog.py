from tkinter import IntVar, Tk, Toplevel
from tkinter.ttk import Button, Frame
from typing import Literal

from .responsive_textbox import ResponsiveTextbox


class YesNoDialog(Toplevel):
    def __init__(
        self,
        tk: Tk,
        title: str,
        prompt: str,
        default_answer: Literal["yes", "no"],
        background: str,
        foreground: str,
        font: str,
        padx: int,
        pady: int,
    ):
        super().__init__(tk, background=background, padx=padx, pady=pady)

        # This may be called from the main thread, so use IntVar and
        # wait_variable() rather than threading.Event() and event.wait().
        self._choice = False if default_answer == "no" else True
        self._v = IntVar(value=0)

        self.title(title)
        self.protocol(
            "WM_DELETE_WINDOW",
            (
                self._handle_select_no
                if default_answer == "no"
                else self._handle_select_yes
            ),
        )
        self.columnconfigure(index=0, weight=1)
        self.rowconfigure(index=0, weight=1)
        frame = Frame(self, padding=20)
        frame.grid(row=0, column=0, sticky="NSEW")
        frame.columnconfigure(index=0, weight=1)
        frame.rowconfigure(index=0, weight=1)
        question_box = ResponsiveTextbox(
            frame,
            width=20,
            font=font,
            background=background,
            foreground=foreground,
            allow_entry=False,
        )
        question_box.grid(row=0, column=0, sticky="NEW")
        question_box.set_text(prompt)
        button_row = Frame(frame)
        button_row.grid(row=1, column=0, sticky="SEW")
        button_row.columnconfigure(index=0, weight=1)
        button_row.columnconfigure(index=1, weight=1)
        ok_btn = Button(button_row, text="Yes", command=self._handle_select_yes)
        ok_btn.grid(row=0, column=0, sticky="EW", padx=10, pady=10)
        no_btn = Button(button_row, text="No", command=self._handle_select_no)
        no_btn.grid(row=0, column=1, sticky="EW", padx=10, pady=10)

    def wait_for_answer(self) -> bool:
        self.wait_variable(self._v)
        return self._choice

    # TODO: Override the destroy() method to set the variable?

    def _handle_select_yes(self) -> None:
        self._choice = True
        self._v.set(1)

    def _handle_select_no(self) -> None:
        self._choice = False
        self._v.set(1)
