"""
Code for handling configuration.
"""

# pyright: reportUnusedImport=false

from .src.config import Config, activate_profile, get_active_profile, list_profiles
from .src.image_style import (
    Bbox,
    Colour,
    Font,
    FooterSlideStyle,
    NoFooterSlideStyle,
    Rectangle,
    Textbox,
)
from .src.mcr_setup_config import McrSetupConfig
from .src.mcr_teardown_config import McrTeardownArgs, McrTeardownConfig
