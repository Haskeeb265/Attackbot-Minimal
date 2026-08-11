"""github-subdomains — subdomain enumeration via GitHub code search (gwen001).

Requires the ``GITHUB_TOKEN`` environment variable on the host; it is
forwarded into the container automatically when set.
"""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = None, output=None) -> int:
    return run_in_docker(
        ["github-subdomains", "-d", target, "-q"],
        env=["GITHUB_TOKEN"],
        timeout=timeout,
        output=output,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_github_subdomains.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
