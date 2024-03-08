from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

import config
from args import McrSetupArgs, ReccArgs
from config import Config, McrSetupConfig, McrTeardownArgs, McrTeardownConfig
from generate_slides import GenerateSlidesArgs, GenerateSlidesConfig


def list_profiles() -> None:
    active_profile = config.get_active_profile()
    for p in sorted(config.list_profiles()):
        if active_profile == p:
            print(f"* {p} <-- active")
        else:
            print(f"* {p}")


def activate_profile(profile: str) -> None:
    config.activate_profile(profile)
    print(f"The active profile is now '{config.get_active_profile()}'.")


def show_config(profile: Optional[str]) -> None:
    cfg = Config(ReccArgs.parse([]), profile=profile, strict=False)
    data = cfg.dump()
    max_key_width = max(len(k) for k in data.keys())
    print(f"{'KEY':<{max_key_width}s} | VALUE")
    for k, v in sorted(data.items()):
        print(f"{k:<{max_key_width}s} | {v}")


def test_load_one_config(profile: Optional[str]) -> None:
    try:
        Config(ReccArgs.parse([]), profile=profile, strict=True)
    except Exception as e:
        raise RuntimeError("Failed to load general configuration.") from e
    try:
        GenerateSlidesConfig(GenerateSlidesArgs.parse([]), profile=profile, strict=True)
    except Exception as e:
        raise RuntimeError("Failed to load configuration for generating slides.") from e
    try:
        McrSetupConfig(McrSetupArgs.parse([]), profile=profile, strict=True)
    except Exception as e:
        raise RuntimeError("Failed to load configuration for MCR setup.") from e
    try:
        McrTeardownConfig(McrTeardownArgs.parse([]), profile=profile, strict=True)
    except Exception as e:
        raise RuntimeError("Failed to load configuration for MCR teardown.") from e


def test_load_all_configs(test_current: bool = True) -> None:
    profiles = sorted(config.list_profiles())
    if test_current:
        if config.get_active_profile() is None:
            script_name = Path(__file__).name
            raise ValueError(
                "No profile is currently active. "
                f"Run 'python {script_name} activate' to choose a profile."
            )
        profiles = [None] + profiles
    for profile in profiles:
        if profile is None:
            print("Testing loading using current profile: ", end="")
        else:
            print(f"Testing loading using profile '{profile}': ", end="")
        test_load_one_config(profile)
        print("OK")


if __name__ == "__main__":
    parser = ArgumentParser(description="Manage script configuration.")
    subparsers = parser.add_subparsers(dest="subcommand")

    list_parser = subparsers.add_parser(
        "list",
        help="Show the list of all available profiles.",
    )

    show_parser = subparsers.add_parser(
        "show",
        help="Show all configuration values for a profile.",
    )
    show_parser.add_argument(
        "--profile",
        "-p",
        required=False,
        help="The name of the profile to show.",
    )

    activate_parser = subparsers.add_parser(
        "activate",
        help="Activate a configuration profile.",
    )
    activate_parser.add_argument(
        "profile",
        help="The name of the profile to activate.",
    )

    test_parser = subparsers.add_parser(
        "test",
        help="Test that the configuration can be loaded.",
    )

    args = parser.parse_args()
    if args.subcommand == "test":
        test_load_all_configs()
    elif args.subcommand == "activate":
        activate_profile(args.profile)
    elif args.subcommand == "show":
        show_config(args.profile)
    elif args.subcommand == "list":
        list_profiles()
    elif args.subcommand is None:
        parser.print_usage()
    else:
        parser.error(f"Unrecognized subcommand '{args.subcommand}'.")
