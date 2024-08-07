from typing import List, Optional

class ElementChildIterator:
    def __next__(self) -> _Element: ...

class _Element:
    def get(self, key: str) -> str: ...
    @property
    def tag(self) -> str: ...
    @property
    def text(self) -> Optional[str]: ...
    @property
    def tail(self) -> Optional[str]: ...
    def xpath(self, _path: str) -> List[_Element]: ...
    def __iter__(self) -> ElementChildIterator: ...

def HTML(text: str) -> _Element: ...
