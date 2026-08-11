"""waybackurls — fetch URLs from the Wayback Machine (tomnomnom).

The tool reads the target from stdin, so the target is piped into the
container: ``echo <target> | waybackurls``.
"""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = None, output=None) -> int:
    return run_in_docker(
        ["waybackurls"],
        timeout=timeout,
        output=output,
        input_data=f"{target}\n",
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_waybackurls.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
