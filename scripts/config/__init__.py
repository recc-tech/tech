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
    activate_profile,
    get_active_profile,
    list_profiles,
)
from .mcr_setup_config import McrSetupConfig
from .mcr_teardown_config import McrTeardownArgs, McrTeardownConfig
