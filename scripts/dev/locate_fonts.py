# TODO: Move other things (e.g., manage_config.py, the scripts to show accuracy
# of caption removal) into dev/ as well? Don't forget to find all references to
# those scripts (e.g., manage_config.py in README) and update them.

# TODO: If we do end up hard-coding font paths, we'll need to update the setup
# instructions to include locating the fonts.

from pathlib import Path
from typing import Iterable, Literal

from args import ReccArgs
from config import Config
from matplotlib.font_manager import FontManager, FontProperties


def _find_font(
    family: Iterable[str],
    style: Literal["normal", "italic", "oblique"],
    manager: FontManager,
) -> Path:
    p = FontProperties(family=family, style=style)
    return Path(manager.findfont(p))


def main() -> None:
    args = ReccArgs.parse([])
    config = Config(args)
    font_manager = FontManager()
    print(
        "Normal: ",
        _find_font(family=config.font_family, style="normal", manager=font_manager),
    )
    print(
        "Italic: ",
        _find_font(family=config.font_family, style="italic", manager=font_manager),
    )
    print(
        "Oblique:",
        _find_font(family=config.font_family, style="oblique", manager=font_manager),
    )


if __name__ == "__main__":
    main()
