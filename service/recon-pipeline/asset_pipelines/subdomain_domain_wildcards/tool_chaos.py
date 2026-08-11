"""chaos — subdomain enumeration from ProjectDiscovery's Chaos dataset.

Requires the ``PDCP_API_KEY`` environment variable on the host; it is
forwarded into the container automatically when set.
"""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = None, output=None) -> int:
    return run_in_docker(
        ["chaos", "-d", target, "-silent"],
        env=["PDCP_API_KEY"],
        timeout=timeout,
        output=output,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_chaos.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
