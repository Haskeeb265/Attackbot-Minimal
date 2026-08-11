"""subfinder — fast passive subdomain enumeration (ProjectDiscovery)."""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = None, output=None) -> int:
    return run_in_docker(
        ["subfinder", "-d", target, "-silent"],
        timeout=timeout,
        output=output,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_subfinder.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
