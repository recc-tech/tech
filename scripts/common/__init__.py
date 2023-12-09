"""
Code that is shared by the packages for multiple scripts.
"""

# Ignore the unused import warnings
# pyright: basic

from common.config import ReccConfig
from common.credentials import Credential, CredentialStore, InputPolicy
from common.parsing_helpers import parse_directory, parse_file, parse_non_empty_string
from common.planning_center import Attachment, Plan, PlanningCenterClient
from common.startup import run_with_or_without_terminal
from common.web_driver import ReccWebDriver
