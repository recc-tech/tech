from args import McrSetupArgs, ReccArgs
from config import Config, McrSetupConfig, McrTeardownArgs, McrTeardownConfig
from generate_slides import GenerateSlidesArgs, GenerateSlidesConfig


def _show_config(cfg: Config) -> None:
    data = cfg.dump()
    max_key_width = max(len(k) for k in data.keys())
    print(f"{'KEY':<{max_key_width}s} | VALUE")
    for k, v in sorted(data.items()):
        print(f"{k:<{max_key_width}s} | {v}")


# TODO: Add command-line flags to manage local profiles (check for differences
# between profiles, compare profile with currently-active profile, replace
# profile (after confirmation if there's any difference), etc.)
# TODO: Add this to the automated test suite
if __name__ == "__main__":
    try:
        cfg = Config(ReccArgs.parse([]), strict=True)
        _show_config(cfg)
        print()
    except Exception as e:
        raise RuntimeError("Failed to load general configuration.") from e
    try:
        GenerateSlidesConfig(GenerateSlidesArgs.parse([]), strict=True)
    except Exception as e:
        raise RuntimeError("Failed to load configuration for generating slides.") from e
    try:
        McrSetupConfig(McrSetupArgs.parse([]), strict=True)
    except Exception as e:
        raise RuntimeError("Failed to load configuration for MCR setup.") from e
    try:
        McrTeardownConfig(McrTeardownArgs.parse([]), strict=True)
    except Exception as e:
        raise RuntimeError("Failed to load configuration for MCR teardown.") from e
    print("Everything looks ok!")
