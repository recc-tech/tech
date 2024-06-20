from __future__ import annotations

import subprocess
import warnings
from dataclasses import dataclass
from enum import Enum
from tkinter import Event, Misc, Text, Tk
from tkinter.ttk import Frame, Label
from typing import Any, Dict, List, Tuple, Union


@dataclass
class PlainText:
    text: str


@dataclass
class UrlText:
    text: str
    url: str


class TextStyle(Enum):
    EMPH = "emph"
    RIGHT_ALIGN = "rjust"

    def __repr__(self) -> str:
        return f"TextStyle.{self.name}"


@dataclass
class StyledText:
    text: str
    styles: List[TextStyle]


TextChunk = Union[PlainText, UrlText, StyledText]


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
        hyperlink_color: str = "cyan",
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

        # Tag styles
        self.tag_configure("url", foreground=hyperlink_color, underline=True)
        self.tag_bind("url", "<Enter>", lambda _: self._set_cursor_hand())
        self.tag_bind("url", "<Leave>", lambda _: self._set_cursor_normal())
        self.tag_bind("url", "<Button-1>", self._on_click_hyperlink)
        self.tag_configure(TextStyle.EMPH.value, underline=True)
        self.tag_configure(TextStyle.RIGHT_ALIGN.value, justify="right")
        self.url_by_tag: Dict[str, str] = {}
        self.next_unique_int = 0

    def set_text(self, text: str) -> None:
        chunks = parse(text)
        self.config(state="normal")
        self.delete(1.0, "end")
        for c in chunks:
            match c:
                case PlainText(_):
                    tags = []
                case StyledText(_, styles):
                    tags = [s.value for s in styles]
                case UrlText(_, url):
                    tag = f"url:{self._get_unique_int()}"
                    self.url_by_tag[tag] = url
                    tags = ["url", tag]
            self.insert("insert", c.text, tags)
        if not self._allow_entry:
            self.config(state="disabled")
        self.resize()

    @property
    def height(self) -> int:
        return self.tk.call((self, "count", "-update", "-displaylines", "1.0", "end"))

    def resize(self) -> None:
        self.configure(height=self.height)

    def _get_unique_int(self) -> int:
        n = self.next_unique_int
        self.next_unique_int += 1
        return n

    def _set_cursor_hand(self) -> None:
        self.config(cursor="hand2")

    def _set_cursor_normal(self) -> None:
        self.config(cursor="arrow")

    def _on_click_hyperlink(self, _: Event[Text]) -> None:
        # Based on https://github.com/GregDMeyer/PWman/blob/master/tkHyperlinkManager.py
        tags = [t for t in self.tag_names("current") if t.startswith("url:")]
        if len(tags) == 1:
            url = self.url_by_tag[tags[0]]
            subprocess.run(["firefox", url])
        elif len(tags) == 0:
            warnings.warn("No tags found for the clicked hyperlink.")
        else:
            warnings.warn("Multiple tags found for the clicked hyperlink.")


def parse(text: str, /) -> List[TextChunk]:
    """
    Split a piece of text into chunks that will each be styled separately.

    ## Examples

    Plain text will appear as-is.
    >>> parse("Hello there!")
    [PlainText(text='Hello there!')]

    Hyperlinks can be included in text as follows.
    >>> parse("My URL is [[url|https://example.com]]...")
    [PlainText(text='My URL is '), UrlText(text='https://example.com', url='https://example.com'), PlainText(text='...')]

    The hyperlink can optionally point to a URL that's different from the
    displayed text.
    >>> parse("[[url|https://example.com|example|hi|hi]]")
    [UrlText(text='example|hi|hi', url='https://example.com')]

    Text can be emphasized.
    >>> parse("This is [[styled|emph|essential]] information.")
    [PlainText(text='This is '), StyledText(text='essential', styles=[TextStyle.EMPH]), PlainText(text=' information.')]

    Text can be right-aligned.
    >>> parse("This text is [[styled|rjust|right-aligned!]]")
    [PlainText(text='This text is '), StyledText(text='right-aligned!', styles=[TextStyle.RIGHT_ALIGN])]

    Text can have multiple styles at once!
    >>> parse("This one is [[styled|emph,rjust|important and also right-aligned!]]")
    [PlainText(text='This one is '), StyledText(text='important and also right-aligned!', styles=[TextStyle.EMPH, TextStyle.RIGHT_ALIGN])]

    ## Invalid Examples

    Invalid inputs should result in a warning but still produce reasonable
    outputs (usually by considering the offending chunk to be plain text).
    >>> import warnings
    >>> def show_output(f):   warnings.filterwarnings("ignore"); return f()
    >>> def show_warnings(f): warnings.filterwarnings("error");  return f()

    The display text for a hyperlink should not be blank.
    >>> f = lambda: parse("[[url|https://example.com| ]]")
    >>> show_output(f)
    [UrlText(text='https://example.com', url='https://example.com')]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: Blank display text in hyperlink "[[url|https://example.com| ]]".

    Styled text should not be blank.
    >>> f = lambda: parse("[[styled|emph|  ]]")
    >>> show_output(f)
    [StyledText(text='  ', styles=[TextStyle.EMPH])]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: Blank styled text "[[styled|emph|  ]]".

    A styled chunk needs a list of styles.
    >>> f = lambda: parse("[[styled|hello there!]]")
    >>> show_output(f)
    [PlainText(text='hello there!')]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: No styles specified in "[[styled|hello there!]]".

    A styled chunk needs a list of styles.
    >>> f = lambda: parse("[[styled||hello there!]]")
    >>> show_output(f)
    [PlainText(text='hello there!')]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: No styles specified in "[[styled||hello there!]]".

    The style must be valid.
    >>> f = lambda: parse("[[styled|foo|hi]]")
    >>> show_output(f)
    [PlainText(text='hi')]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: Unknown style "foo".

    The style must be valid.
    >>> f = lambda: parse("[[styled|emph,bar|hi]]")
    >>> show_output(f)
    [StyledText(text='hi', styles=[TextStyle.EMPH])]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: Unknown style "bar".

    There should be a closing "]]" for every formatted chunk.
    >>> f = lambda: parse("Unclosed chunk: [[url|https://example.com")
    >>> show_output(f)
    [PlainText(text='Unclosed chunk: [[url|https://example.com')]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: The text "[[url|https://example.com" looks like a formatted text chunk, but it is missing the closing "]]".

    The chunk type must be one of the predefined ones (e.g., "url").
    >>> f = lambda: parse("Invalid type: [[blahblah|hello]]")
    >>> show_output(f)
    [PlainText(text='Invalid type: [[blahblah|hello]]')]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: The chunk type "blahblah" (in text "[[blahblah|hello]]") is unknown.

    >>> f = lambda: parse("[[hi]]...")
    >>> show_output(f)
    [PlainText(text='[[hi]]...')]
    >>> show_warnings(f)
    Traceback (most recent call last):
        ...
    UserWarning: The chunk type "" (in text "[[hi]]") is unknown.
    """
    # TODO: update all previous occurrences of [[emph|...]] (hopefully the tests will catch them all...)
    chunks: List[TextChunk] = []
    current_plain_chunk = ""
    while True:
        if not text:
            chunks.append(PlainText(current_plain_chunk))
            current_plain_chunk = ""
            break
        elif text.startswith("[["):
            chunks.append(PlainText(text=current_plain_chunk))
            current_plain_chunk = ""
            c, text = _parse_formatted_chunk(text)
            chunks.append(c)
        else:
            current_plain_chunk += text[0]
            text = text[1:]
    assert current_plain_chunk == ""
    chunks = [c for c in chunks if c.text]
    return _merge_plain_chunks(chunks)


def _merge_plain_chunks(chunks: List[TextChunk]) -> List[TextChunk]:
    """
    Merge consecutive plaintext chunks.

    ## Examples
    >>> _merge_plain_chunks([PlainText("fee "), PlainText("fi "), UrlText(text="a ", url="https://example.com"), PlainText("fo "), PlainText("fum")])
    [PlainText(text='fee fi '), UrlText(text='a ', url='https://example.com'), PlainText(text='fo fum')]

    >>> _merge_plain_chunks([])
    []

    >>> _merge_plain_chunks([PlainText(text="hi")])
    [PlainText(text='hi')]

    """
    merged: List[TextChunk] = []
    while chunks:
        next_chunk = chunks.pop(0)
        last_merged = merged[-1] if merged else None
        if isinstance(next_chunk, PlainText) and isinstance(last_merged, PlainText):
            combined = PlainText(text=last_merged.text + next_chunk.text)
            merged = merged[:-1] + [combined]
        else:
            merged.append(next_chunk)
    return merged


def _parse_formatted_chunk(text: str) -> Tuple[TextChunk, str]:
    """
    Parse a chunk that is formatted (i.e., is enclosed in "[[").
    Returns the chunk along with the remaining text after the chunk.

    ## Examples
    Valid URL:
    >>> _parse_formatted_chunk("[[url|https://example.com]] and after")
    (UrlText(text='https://example.com', url='https://example.com'), ' and after')

    Valid URL and display text:
    >>> _parse_formatted_chunk("[[url|https://example.com|hi]]...")
    (UrlText(text='hi', url='https://example.com'), '...')

    Emphasized text:
    >>> _parse_formatted_chunk("[[styled|emph|important!]]")
    (StyledText(text='important!', styles=[TextStyle.EMPH]), '')
    """
    assert text.startswith("[[")
    if "]]" not in text:
        warnings.warn(
            f'The text "{text}" looks like a formatted text chunk, but it is'
            ' missing the closing "]]".'
        )
        return (PlainText(text), "")
    end_idx = text.index("]]")
    chunk_text = text[: (end_idx + 2)]
    remaining_text = text[(end_idx + 2) :]
    bar_idx = chunk_text.index("|", 2) if "|" in chunk_text else 2
    typ = chunk_text[2:bar_idx]
    match typ:
        case "url":
            chunk = _parse_url_chunk(chunk_text[6:-2])
        case "styled":
            chunk = _parse_styled_chunk(chunk_text[9:-2])
        case _:
            warnings.warn(
                f'The chunk type "{typ}" (in text "{chunk_text}") is unknown.'
            )
            chunk = PlainText(text=chunk_text)
    return (chunk, remaining_text)


def _parse_url_chunk(text: str) -> UrlText:
    """
    Parse the contents of a URL chunk.

    ## Examples
    >>> _parse_url_chunk("https://example.com")
    UrlText(text='https://example.com', url='https://example.com')
    >>> _parse_url_chunk("https://example.com|he|he|he")
    UrlText(text='he|he|he', url='https://example.com')
    """
    if "|" in text:
        i = text.index("|")
        display = text[(i + 1) :]
        url = text[:i]
    else:
        url = text
        display = url
    if not display.strip():
        warnings.warn(f'Blank display text in hyperlink "[[url|{text}]]".')
        display = url
    return UrlText(text=display, url=url)


def _parse_styled_chunk(text: str) -> TextChunk:
    """
    Parse the contents of a styled chunk.

    ## Examples
    >>> _parse_styled_chunk("emph|hello there")
    StyledText(text='hello there', styles=[TextStyle.EMPH])
    >>> _parse_styled_chunk("emph,rjust|hello there")
    StyledText(text='hello there', styles=[TextStyle.EMPH, TextStyle.RIGHT_ALIGN])
    """
    if "|" not in text:
        warnings.warn(f'No styles specified in "[[styled|{text}]]".')
        return PlainText(text)
    i = text.index("|")
    contents = text[(i + 1) :]
    if not contents.strip():
        warnings.warn(f'Blank styled text "[[styled|{text}]]".')
    style_strings = [x for x in text[:i].split(",") if x]
    if len(style_strings) == 0:
        warnings.warn(f'No styles specified in "[[styled|{text}]]".')
        return PlainText(text=contents)
    styles: List[TextStyle] = []
    unknown_styles: List[str] = []
    for ss in style_strings:
        try:
            styles.append(TextStyle(ss))
        except ValueError:
            unknown_styles.append(ss)
    for s in unknown_styles:
        warnings.warn(f'Unknown style "{s}".')
    if styles:
        return StyledText(text=contents, styles=styles)
    else:
        return PlainText(text=contents)


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
