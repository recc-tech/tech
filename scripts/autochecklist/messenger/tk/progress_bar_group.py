from threading import Lock
from tkinter import Tk, Toplevel
from tkinter.ttk import Label, Progressbar
from typing import Dict, Tuple


class ProgressBarGroup(Toplevel):
    def __init__(
        self,
        parent: Tk,
        padx: int,
        pady: int,
        width: int,
        background: str,
        foreground: str,
        font: str,
    ) -> None:
        self._tk = parent
        self._background = background
        self._foreground = foreground
        self._font = font
        self._mutex = Lock()
        self._key_gen = 0
        self._bar_by_key: Dict[int, Tuple[Progressbar, Label, Label, float, str]] = {}
        self._length = int(width - 2 * padx)
        super().__init__(
            parent,
            padx=padx,
            pady=pady,
            background=self._background,
            width=width,
        )
        # Disable closing
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self._hide()
        self.title("Progress")

    def create_progress_bar(
        self, display_name: str, max_value: float, units: str
    ) -> int:
        with self._mutex:
            key = self._get_unique_key()
            name_label = Label(
                self,
                text=display_name,
                background=self._background,
                foreground=self._foreground,
                font=self._font,
            )
            name_label.grid(row=2 * key, columnspan=2)
            progress_label = Label(
                self,
                background=self._background,
                foreground=self._foreground,
                text=f"[0.00/{max_value:.2f} {units}]",
                font=self._font,
            )
            progress_label.grid(row=2 * key + 1, column=0)
            bar = Progressbar(
                self,
                length=self._length,
                orient="horizontal",
                mode="determinate",
            )
            bar.grid(row=2 * key + 1, column=1, ipady=20)
            self._bar_by_key[key] = (bar, name_label, progress_label, max_value, units)
            if len(self._bar_by_key.values()) == 1:
                self._tk.update_idletasks()
                self.geometry(f"+{self._tk.winfo_x()}+{self._tk.winfo_y()}")
                self._show()
            return key

    def update_progress_bar(self, key: int, progress: float) -> None:
        with self._mutex:
            try:
                bar, _, label, max_value, units = self._bar_by_key[key]
            except KeyError:
                return
            bar["value"] = min(100, 100 * progress / max_value)
            label.config(text=f"[{progress:.2f}/{max_value:.2f} {units}]")

    def delete_progress_bar(self, key: int) -> None:
        with self._mutex:
            bar = self._bar_by_key.pop(key, None)
            if not bar:
                return
            if len(self._bar_by_key.values()) == 0:
                self._hide()
            (bar, name_label, progress_label, _, _) = bar
            bar.destroy()
            name_label.destroy()
            progress_label.destroy()

    def _show(self) -> None:
        self.deiconify()

    def _hide(self) -> None:
        self.withdraw()

    def _get_unique_key(self) -> int:
        self._key_gen += 1
        return self._key_gen
