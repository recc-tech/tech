from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from pathlib import Path
from typing import Optional

import config
from args import McrTeardownArgs, ReccArgs
from config import Config, McrSetupConfig, McrTeardownConfig
from generate_slides import GenerateSlidesArgs, GenerateSlidesConfig


def list_profiles() -> None:
    active_profile = config.get_active_profile()
    all_profiles = config.list_profiles()
    n = max(len(p) for p in all_profiles)
    for p in sorted(all_profiles):
        path = config.locate_profile(p).relative_to(Path(".").resolve())
        s = f"{p:<{n}s} ({path.as_posix()})"
        if active_profile == p:
            s = f"active > {s}"
        else:
            s = f"         {s}"
        print(s)


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
        Config(
            ReccArgs.parse([]),
            profile=profile,
            strict=True,
            allow_multiple_only_for_testing=True,
        )
    except Exception as e:
        raise RuntimeError("Failed to load general configuration.") from e
    try:
        GenerateSlidesConfig(
            GenerateSlidesArgs.parse([]),
            profile=profile,
            strict=True,
            allow_multiple_only_for_testing=True,
        )
    except Exception as e:
        raise RuntimeError("Failed to load configuration for generating slides.") from e
    try:
        McrSetupConfig(
            ReccArgs.parse([]),
            profile=profile,
            strict=True,
            allow_multiple_only_for_testing=True,
        )
    except Exception as e:
        raise RuntimeError("Failed to load configuration for MCR setup.") from e
    try:
        McrTeardownConfig(
            McrTeardownArgs.parse([]),
            profile=profile,
            strict=True,
            allow_multiple_only_for_testing=True,
        )
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
    parser = ArgumentParser(
        description="manage script configuration",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    list_parser = subparsers.add_parser(
        "list",
        help="show the list of all available profiles",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )

    show_parser = subparsers.add_parser(
        "show",
        help="show all configuration values for a profile",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    show_parser.add_argument(
        "--profile",
        "-p",
        required=False,
        help="name of the profile to show",
    )

    activate_parser = subparsers.add_parser(
        "activate",
        help="activate a configuration profile",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    activate_parser.add_argument(
        "--profile",
        "-p",
        required=False,
        default=config.get_default_profile(),
        help="name of the profile to activate",
    )

    test_parser = subparsers.add_parser(
        "test",
        help="test that the configuration can be loaded",
        formatter_class=ArgumentDefaultsHelpFormatter,
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
