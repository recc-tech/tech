"""
Code for handling configuration.
"""

# pyright: reportUnusedImport=false

from .config import (
    Bbox,
    Config,
    Font,
    FooterSlideStyle,
    NoFooterSlideStyle,
    Rectangle,
    Textbox,
)
from .mcr_setup_config import McrSetupArgs, McrSetupConfig
from .mcr_teardown_config import (
    McrTeardownArgs,
    McrTeardownConfig,
    parse_boxcast_event_url,
)
from .parsing_helpers import parse_directory, parse_file, parse_non_empty_string
from .recc_args import ReccArgs
