from tkinter import IntVar, Tk, Toplevel
from tkinter.ttk import Button, Frame
from typing import Callable, Generic, List, Optional, Tuple, TypeVar

from ..input_messenger import ListChoice
from .responsive_textbox import ResponsiveTextbox

T = TypeVar("T")


class ListInputDialog(Toplevel, Generic[T]):
    def __init__(
        self,
        tk: Tk,
        title: str,
        prompt: str,
        choices: List[ListChoice[T]],
        background: str,
        foreground: str,
        font: str,
        padx: int,
        pady: int,
    ):
        super().__init__(tk, background=background, padx=padx, pady=pady)

        self._is_destroyed = False
        self._choice: Optional[Tuple[ListChoice[T], ResponsiveTextbox]] = None
        self._v = IntVar(value=0)

        def handle_close() -> None:
            self._choice = None
            self._v.set(1)

        self.title(title)
        self.protocol("WM_DELETE_WINDOW", handle_close)
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

        options_box = Frame(frame)
        options_box.grid(row=1, column=0, sticky="EW", padx=padx, pady=pady)
        for i, c in enumerate(choices):
            c_box = ResponsiveTextbox(
                options_box,
                width=20,
                font=font,
                background=background,
                foreground=foreground,
                allow_entry=False,
                padx=padx / 2,
                pady=pady / 2,
                borderwidth=2,
                relief="ridge",
            )
            c_box.grid(row=i, column=0, sticky="NEW")
            c_box.set_text(c.display)

            def make_handler(
                c: ListChoice[T], c_box: ResponsiveTextbox
            ) -> Callable[[object], None]:
                def f(_: object) -> None:
                    if self._choice is not None:
                        self._choice[1].configure(foreground=foreground)
                    self._choice = (c, c_box)
                    c_box.configure(foreground="red")

                return f

            c_box.bind("<Button-1>", make_handler(c, c_box))
        c = None
        c_box = None

        def handle_ok() -> None:
            self._v.set(1)

        btn = Button(frame, text="Ok", command=handle_ok)
        btn.grid(row=2, column=0, sticky="EW", padx=10, pady=10)

    def wait_for_answer(self) -> Optional[T]:
        self.wait_variable(self._v)
        return None if self._choice is None else self._choice[0].value

    def destroy(self) -> None:
        if self._is_destroyed:
            return
        self._is_destroyed = True
        super().destroy()
        # Set the variable so that tkinter can break out of the local loop in
        # wait_variable()
        self._v.set(1)
