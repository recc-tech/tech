import subprocess
import sys
from typing import List

RED = "\033[0;31m"
GREEN = "\033[0;32m"
RESET_COLOR = "\033[0m"


def main():
    error = False
    all_tags = _get_tags()
    tags = sorted(all_tags, reverse=True)[:5]

    print("AVAILABLE VERSIONS:")
    print(" * latest")
    for t in tags:
        print(f" * {t}")

    tag = input("\nSELECT THE VERSION TO USE:\n> ")
    tag = tag.lower()
    match tag:
        case "latest":
            _check_out_latest()
            print(f"{GREEN}OK: currently on the latest version.{RESET_COLOR}")
        case _ if tag in tags:
            _check_out_tag(tag)
            current_tag = _get_current_tag()
            print(f"{GREEN}OK: currently on version {current_tag}.{RESET_COLOR}")
        case _:
            error = True
            print(f"{RED}Invalid choice.{RESET_COLOR}", file=sys.stderr)

    input("Press ENTER to exit...")
    if error:
        sys.exit(255)


def _get_tags() -> List[str]:
    result = subprocess.run(
        ["git", "tag", "--list"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    out = result.stdout
    return [l.lower() for l in out.split("\n") if l]


def _check_out_latest() -> None:
    subprocess.run(["git", "switch", "main"], check=True, capture_output=True)


def _check_out_tag(tag: str) -> None:
    subprocess.run(
        ["git", "checkout", f"tags/{tag}", "--force"], check=True, capture_output=True
    )


def _get_current_tag() -> str:
    result = subprocess.run(
        ["git", "describe", "--exact-match"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


if __name__ == "__main__":
    main()
