from config import (
    Config,
    McrSetupArgs,
    McrSetupConfig,
    McrTeardownArgs,
    McrTeardownConfig,
    ReccArgs,
)
from generate_slides import GenerateSlidesArgs, GenerateSlidesConfig

# TODO: Add command-line flags to manage local profiles (check for differences
# between profiles, compare profile with currently-active profile, replace
# profile (after confirmation if there's any difference), etc.)
# TODO: Add this to the automated test suite
if __name__ == "__main__":
    try:
        Config(ReccArgs.parse([]), strict=True)
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
