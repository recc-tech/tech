from config import Config, ReccArgs

# TODO: Add command-line flags to manage local profiles (check for differences
# between profiles, compare profile with currently-active profile, replace
# profile (after confirmation if there's any difference), etc.)
# TODO: Add this to the automated test suite
if __name__ == "__main__":
    try:
        Config(ReccArgs.parse([]), strict=True)
        print("Everything looks ok!")
    except ValueError as e:
        exit(f"An error occurred: {e}")
