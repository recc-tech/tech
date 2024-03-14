from __future__ import annotations

import typing
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, Namespace
from typing import Callable, Dict, List, Literal, Optional, Set, Type, TypeVar

T = TypeVar("T", bound="BaseArgs")


class BaseArgs:
    """Command-line arguments."""

    NAME = ""
    DESCRIPTION = ""

    def __init__(self, args: Namespace, error: Callable[[str], None]) -> None:
        if args.auto is not None:
            if "none" in args.auto and len(args.auto) > 1:
                error("If 'none' is included in --auto, it must be the only value.")
            if args.auto == ["none"]:
                args.auto = typing.cast(Set[str], set())

        self.ui: Literal["console", "tk"] = args.ui
        self.verbose: bool = args.verbose
        self.no_run: bool = args.no_run
        self.auto_tasks: Optional[Set[str]] = args.auto
        """
        Whitelist of tasks that can be automated. `None` means all tasks that
        can be automated should be automated.
        """

    @classmethod
    def set_up_parser(cls, parser: ArgumentParser) -> None:
        common_args = parser.add_argument_group("Common arguments")
        common_args.add_argument(
            "--ui",
            choices=["console", "tk"],
            default="tk",
            help="User interface to use.",
        )
        common_args.add_argument(
            "--verbose",
            action="store_true",
            help="This flag is only applicable when the console UI is used. It makes the script show updates on the status of each task. Otherwise, the script will only show messages for warnings or errors.",
        )
        common_args.add_argument(
            "--no-run",
            action="store_true",
            help="If this flag is provided, the task graph will be loaded but the tasks will not be run. This may be useful for checking that the JSON task file and command-line arguments are valid.",
        )
        common_args.add_argument(
            "--auto",
            action="append",
            default=None,
            help="Specify which tasks to automate. You can also provide 'none' to automate none of the tasks. By default, all tasks that can be automated are automated.",
        )

    @classmethod
    def parse(cls: Type[T], args: List[str]) -> T:
        parser = ArgumentParser(
            prog=cls.NAME,
            description=cls.DESCRIPTION,
            formatter_class=ArgumentDefaultsHelpFormatter,
        )
        cls.set_up_parser(parser)
        if len(args) >= 1:
            # Skip the program name
            args = args[1:]
        return cls(parser.parse_args(args), parser.error)

    def dump(self) -> Dict[str, str]:
        return {"UI": self.ui}
