"""
Code for handling configuration.
"""

# pyright: reportUnusedImport=false

from .src.config import (
    Bbox,
    Colour,
    Config,
    Font,
    FooterSlideStyle,
    NoFooterSlideStyle,
    Rectangle,
    Textbox,
    activate_profile,
    get_active_profile,
    list_profiles,
)
from .src.mcr_setup_config import McrSetupConfig
from .src.mcr_teardown_config import McrTeardownArgs, McrTeardownConfig
