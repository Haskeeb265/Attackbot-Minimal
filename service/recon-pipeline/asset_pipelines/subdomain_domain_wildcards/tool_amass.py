"""amass — passive subdomain enumeration (OWASP Amass)."""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = 2400, output=None) -> int:
    return run_in_docker(
        ["amass", "enum", "-passive", "-d", target],
        timeout=timeout,
        output=output,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_amass.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
