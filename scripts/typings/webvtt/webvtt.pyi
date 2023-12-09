"""
This type stub file was generated by pyright.
"""

from pathlib import Path
from typing import List, Optional

from .structures import Caption

class WebVTT:
    """
    Parse captions in WebVTT format and also from other formats like SRT.

    To read WebVTT:

        WebVTT().read('captions.vtt')

    For other formats like SRT, use from_[format in lower case]:

        WebVTT().from_srt('captions.srt')

    A list of all supported formats is available calling list_formats().
    """

    def __init__(
        self,
        file: str = "",
        captions: Optional[List[Caption]] = None,
        styles: None = None,
    ) -> None: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> Caption: ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...
    @classmethod
    def read(cls, file: Path) -> WebVTT: ...
    def save(self, output: Path) -> None: ...
    @property
    def captions(self) -> list[Caption]: ...
    @property
    def total_length(self) -> int: ...