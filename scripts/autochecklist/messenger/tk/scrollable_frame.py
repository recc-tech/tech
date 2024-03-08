from __future__ import annotations

from tkinter import Button, Canvas, Event, Frame, Misc, Scrollbar, Text, Tk
from typing import Any


class ScrollableFrame(Frame):
    def __init__(
        self, parent: Misc, padding: int, background: str, scrollbar_width: int
    ) -> None:
        self._root = parent.winfo_toplevel()

        self.outer_frame = Frame(parent, background=background)
        self.outer_frame.rowconfigure(index=0, weight=1)
        self.outer_frame.columnconfigure(index=0, weight=1)

        self._canvas = Canvas(self.outer_frame, background=background)
        self._canvas.grid(row=0, column=0, sticky="NSEW")

        self._scrollbar = Scrollbar(
            self.outer_frame,
            orient="vertical",
            command=self._canvas.yview,
            width=scrollbar_width,
        )
        self._scrollbar.grid(row=0, column=1, sticky="NSE")

        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.bind("<Configure>", self._on_resize_canvas)

        # Allow scrolling with the mouse (why does this not work out of the box? D:<<)
        # TODO: This doesn't seem to work, at least on Linux
        self._root.bind_all(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )

        super().__init__(
            self._canvas, padx=padding, pady=padding, background=background
        )

    def resize(self) -> None:
        # Make sure the display has updated before recomputing the scrollregion
        self._root.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_resize_canvas(self, _: Event[Canvas]) -> None:
        c = self._canvas
        c.create_window((0, 0), window=self, anchor="nw", width=c.winfo_width())
        self.resize()

    def pack_configure(self, *args: Any, **kwargs: Any) -> None:
        return self.outer_frame.pack_configure(*args, **kwargs)

    pack = configure = config = pack_configure  # pyright: ignore

    def grid_configure(self, *args: Any, **kwargs: Any) -> None:
        return self.outer_frame.grid_configure(*args, **kwargs)

    def place_configure(self, *args: Any, **kwargs: Any) -> None:
        return self.outer_frame.place_configure(*args, **kwargs)


if __name__ == "__main__":
    BACKGROUND = "#323232"
    i = 1

    def add_label(frame: ScrollableFrame) -> None:
        global i
        lab1 = Text(frame, width=10, height=1, background="red")
        lab1.grid(row=i, column=0, padx=5, pady=5, sticky="NEW")
        lab2 = Text(frame, width=30, height=1, background="red")
        lab2.grid(row=i, column=1, padx=5, pady=5, sticky="NEW")
        lab2.insert("end", f"({i}) Hello there! Here is some text.")
        frame.resize()
        i = i + 1

    root = Tk()
    root.geometry("500x500")
    root.config(background=BACKGROUND)
    frame = ScrollableFrame(root, padding=25, background=BACKGROUND, scrollbar_width=25)
    frame.pack(fill="both", expand=1)
    frame.columnconfigure(index=1, weight=1)
    add_btn = Button(frame, text="Add row", command=lambda: add_label(frame))
    add_btn.grid(row=0)
    root.mainloop()
