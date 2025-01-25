import platform
import subprocess
import unittest
from pathlib import Path
from test.mock import MockInputMessenger
from typing import TypeVar
from unittest.mock import create_autospec

import check_credentials
import download_pco_assets
import generate_slides
import launch_apps
import mcr_setup
import mcr_teardown
import summarize_plan
from args import McrTeardownArgs, ReccArgs
from autochecklist import FileMessenger, Messenger, ProblemLevel, TaskStatus
from check_credentials import CheckCredentialsArgs
from config import Config, McrSetupConfig, McrTeardownConfig
from download_pco_assets import DownloadAssetsArgs
from external_services import CredentialStore
from generate_slides import GenerateSlidesArgs, GenerateSlidesConfig
from launch_apps import LaunchAppsArgs
from lib import ReccDependencyProvider
from mcr_setup import McrSetupArgs
from summarize_plan import SummarizePlanArgs

from .startup_smoke_test_data import (
    broken_task_graph,
    missing_dependency,
    unused_function,
)

T = TypeVar("T")

_LOG_FILE = Path(__file__).parent.joinpath("startup_smoke_test_data", "test.log")
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent
_HELP_DIR = Path(__file__).parent.joinpath("help_messages")


class MockDependencyProvider(ReccDependencyProvider):
    def __init__(self, *, args: check_credentials.ReccArgs, config: Config) -> None:
        file_messenger = FileMessenger(_LOG_FILE)
        self.input_messenger = MockInputMessenger()
        messenger = Messenger(file_messenger, self.input_messenger)
        super().__init__(
            args=args,
            config=config,
            messenger=messenger,
            log_file=_LOG_FILE,
            script_name="test",
            description="test",
            show_statuses_by_default=True,
            lazy_login=True,
        )
        self._credentials_mock = create_autospec(CredentialStore)

    def get(self, typ: type[object]) -> object:
        if typ == CredentialStore:
            return self._credentials_mock
        else:
            return super().get(typ)


class PyStartupSmokeTestCase(unittest.TestCase):
    """
    Smoke tests to ensure all scripts can at least start without errors or
    warnings.
    For example, this should automatically catch mistakes in the task graphs.
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_broken_task_graph(self) -> None:
        """Make sure this test suite can catch broken task graph."""
        args = ReccArgs.parse([""])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        broken_task_graph.main(args, config, dep)
        self.assertEqual(
            [
                (
                    "SCRIPT MAIN",
                    ProblemLevel.FATAL,
                    "Failed to load the task graph: The prerequisite 'missing' could not be found.",
                )
            ],
            dep.input_messenger.errors,
        )

    def test_missing_dependency(self) -> None:
        """Make sure this test suite can catch missing inputs to functions."""
        args = ReccArgs.parse([""])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        missing_dependency.main(args, config, dep)
        self.assertEqual(
            [
                (
                    "SCRIPT MAIN",
                    ProblemLevel.FATAL,
                    "Failed to load the task graph: Failed to find arguments for function 'missing_dependency' (Unknown argument type MyService).",
                )
            ],
            dep.input_messenger.errors,
        )

    def test_unused_function(self) -> None:
        """Make sure this test suite can catch unused functions."""
        args = ReccArgs.parse([""])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        unused_function.main(args, config, dep)
        self.assertEqual(
            [
                (
                    "SCRIPT MAIN",
                    ProblemLevel.WARN,
                    "The following functions are not used by any task: unused",
                )
            ],
            dep.input_messenger.errors,
        )

    def test_check_credentials(self) -> None:
        args = CheckCredentialsArgs.parse(["", "--no-run"])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        check_credentials.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_download_pco_assets(self) -> None:
        args = DownloadAssetsArgs.parse(["", "--no-run"])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        download_pco_assets.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_generate_slides(self) -> None:
        args = GenerateSlidesArgs.parse(["", "--no-run"])
        config = GenerateSlidesConfig(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        generate_slides.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_launch_apps_all(self) -> None:
        apps = list(launch_apps.App)
        args = LaunchAppsArgs.parse(["", "--no-run"] + [a.value for a in apps])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        launch_apps.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_launch_apps_foh(self) -> None:
        args = LaunchAppsArgs.parse(["", "pco", "foh_setup_checklist", "--no-run"])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        launch_apps.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_launch_apps_mcr(self) -> None:
        args = LaunchAppsArgs.parse(
            [
                "",
                "pco",
                "boxcast",
                "cop",
                "vmix",
                "mcr_setup_checklist",
                "mcr_teardown_checklist",
                "--no-run",
            ]
        )
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        launch_apps.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_mcr_setup(self) -> None:
        args = McrSetupArgs.parse(["", "--no-run"])
        config = McrSetupConfig(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        mcr_setup.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_mcr_teardown(self) -> None:
        args = McrTeardownArgs.parse(["", "--no-run"])
        config = McrTeardownConfig(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        mcr_teardown.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )

    def test_summarize_plan(self) -> None:
        args = SummarizePlanArgs.parse(["", "--no-run"])
        config = Config(args, allow_multiple_only_for_testing=True)
        dep = MockDependencyProvider(args=args, config=config)
        summarize_plan.main(args, config, dep)
        self.assertEqual([], dep.input_messenger.errors)
        self.assertEqual(
            (
                "SCRIPT MAIN",
                TaskStatus.DONE,
                "No tasks were run because no_run = true.",
            ),
            dep.input_messenger.statuses[-1],
        )


class CommandStartupTestCase(unittest.TestCase):
    """
    Smoke tests to ensure that the .command scripts work as expected.
    For example, this should catch startup errors due to incorrect file paths.
    """

    def setUp(self) -> None:
        self.maxDiff = None
        p = platform.system()
        match p:
            case "Darwin" | "Linux":
                pass
            case "Windows":
                self.skipTest("Wrong platform.")
            case _:
                self.fail(f"Unrecognized platform '{p}'.")

    def test_download_pco_assets_positive(self) -> None:
        self._test_positive("download_pco_assets")

    def test_download_pco_assets_negative(self) -> None:
        self._test_negative("download_pco_assets")

    def test_launch_apps_positive(self) -> None:
        self._test_positive("launch_apps")

    def test_launch_apps_negative(self) -> None:
        self._test_negative("launch_apps")

    def test_summarize_plan_positive(self) -> None:
        self._test_positive("summarize_plan")

    def test_summarize_plan_negative(self) -> None:
        self._test_negative("summarize_plan")

    def _test_positive(self, name: str) -> None:
        script_path = _SCRIPTS_DIR.joinpath(f"{name}.command")
        help_path = _HELP_DIR.joinpath(f"{name}.txt")
        result = subprocess.run(
            [script_path.resolve().as_posix(), "--help"],
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, help_path.read_text())

    def _test_negative(self, name: str) -> None:
        cmd_path = _SCRIPTS_DIR.joinpath(f"{name}.command").resolve()
        py_path = _SCRIPTS_DIR.joinpath(f"{name}.py").resolve()
        bak_path = _SCRIPTS_DIR.joinpath(f"{name}.py.bak").resolve()
        py_path.rename(bak_path)
        try:
            result = subprocess.run(
                [cmd_path.as_posix(), "--help"],
                capture_output=True,
                encoding="utf-8",
            )
            self.assertNotEqual(result.stderr, "")
            self.assertEqual(result.stdout, "")
        finally:
            bak_path.rename(py_path)
