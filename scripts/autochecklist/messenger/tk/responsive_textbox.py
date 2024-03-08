from __future__ import annotations

from tkinter import Misc, Text, Tk
from tkinter.ttk import Frame, Label
from typing import Any


class ResponsiveTextbox(Text):
    """
    A textbox that can automatically wrap text and maintains the minimum height
    needed to fit that text.
    Unlike a label, it supports selecting and copying text.
    """

    def __init__(
        self,
        parent: Misc,
        width: int,
        font: str,
        background: str,
        foreground: str,
        allow_entry: bool = False,
        **kwargs: Any,
    ) -> None:
        self._allow_entry = allow_entry
        if "highlightthickness" not in kwargs:
            kwargs["highlightthickness"] = 0
        if "borderwidth" not in kwargs:
            kwargs["borderwidth"] = 0
        if "height" in kwargs:
            raise ValueError(f"Cannot set height of {type(self).__name__}.")
        else:
            kwargs["height"] = 1
        if "state" in kwargs:
            raise ValueError(f"Cannot directly set state of {type(self).__name__}.")
        else:
            kwargs["state"] = "normal" if allow_entry else "disabled"
        if "wrap" in kwargs:
            raise ValueError(f"Cannot set wrap of {type(self).__name__}.")
        else:
            kwargs["wrap"] = "word"
        super().__init__(
            parent,
            width=width,
            font=font,
            background=background,
            foreground=foreground,
            **kwargs,
        )
        self.bind("<Configure>", lambda _: self.resize())

    def set_text(self, text: str) -> None:
        self.config(state="normal")
        self.delete(1.0, "end")
        self.insert(1.0, text)
        if not self._allow_entry:
            self.config(state="disabled")
        self.resize()

    @property
    def height(self) -> int:
        return self.tk.call((self, "count", "-update", "-displaylines", "1.0", "end"))

    def resize(self) -> None:
        self.configure(height=self.height)


if __name__ == "__main__":
    root = Tk()

    frame = Frame(root, padding=5)
    frame.pack(expand=True, fill="both")

    frame.columnconfigure(index=1, weight=1)

    label1 = Label(frame, text="Row 1")
    label1.grid(row=0, column=0, sticky="NEW")

    text1 = ResponsiveTextbox(
        frame,
        width=20,
        font=None,  # pyright: ignore[reportArgumentType]
        background=None,  # pyright: ignore[reportArgumentType]
        foreground=None,  # pyright: ignore[reportArgumentType]
    )
    text1.grid(row=0, column=1, sticky="NEW")
    text1.set_text(
        "ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha"
    )

    label2 = Label(frame, text="Row 2")
    label2.grid(row=1, column=0, sticky="NEW")

    text2 = ResponsiveTextbox(
        frame,
        width=20,
        font=None,  # pyright: ignore[reportArgumentType]
        background=None,  # pyright: ignore[reportArgumentType]
        foreground=None,  # pyright: ignore[reportArgumentType]
    )
    text2.grid(row=1, column=1, sticky="NEW")
    text2.set_text(
        "ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha",
    )

    root.mainloop()
