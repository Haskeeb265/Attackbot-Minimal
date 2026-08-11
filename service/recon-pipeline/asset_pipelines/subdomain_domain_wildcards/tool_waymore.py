"""waymore — historical URL harvesting (Wayback Machine, xnl-h4ck3r)."""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = 600, output=None) -> int:
    return run_in_docker(
        ["waymore", "-i", target, "-mode", "U", "-n", "--providers", "wayback"],
        timeout=timeout,
        output=output,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_waymore.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
