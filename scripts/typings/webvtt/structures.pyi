"""
This type stub file was generated by pyright.
"""

from typing import Union

class Caption:
    identifier: Union[str, None]
    def __str__(self) -> str: ...
    def add_line(self, line: str) -> None: ...
    @property
    def start_in_seconds(self) -> float: ...
    @property
    def end_in_seconds(self) -> float: ...
    @property
    def start(self) -> str: ...
    @start.setter
    def start(self, value: str) -> None: ...
    @property
    def end(self) -> str: ...
    @end.setter
    def end(self, value: str) -> None: ...
    @property
    def lines(self) -> list[str]: ...
    @property
    def text(self) -> str: ...
    @property
    def raw_text(self) -> str: ...
    @text.setter
    def text(self, value: str) -> None: ...
