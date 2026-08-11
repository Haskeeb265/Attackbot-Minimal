"""gau — historical URL harvesting from Wayback + Common Crawl (lc/gau)."""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = 1400, output=None) -> int:
    return run_in_docker(
        ["gau", "--subs", "--providers", "wayback,commoncrawl", target],
        timeout=timeout,
        output=output,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_gau.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
