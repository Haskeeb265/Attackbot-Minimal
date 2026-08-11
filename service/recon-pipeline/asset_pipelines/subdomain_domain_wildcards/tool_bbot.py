"""bbot — OSINT subdomain enumeration (Black Lantern Security)."""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = 1000, output=None) -> int:
    return run_in_docker(
        ["bbot", "-t", target, "-p", "subdomain-enum", "-y", "--no-color"],
        timeout=timeout,
        output=output,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_bbot.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
