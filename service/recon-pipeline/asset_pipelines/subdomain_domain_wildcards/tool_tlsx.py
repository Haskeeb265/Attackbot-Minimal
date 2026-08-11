"""tlsx — TLS/SSL certificate probing (ProjectDiscovery).

Runs the three documented probes against the target:
  SAN probe, CN probe, and org + TLS-version probe.
"""

import sys

from runner import run_in_docker


def run(target: str, timeout: int | None = None, output=None) -> int:
    exit_code = 0
    for probe in (["-san"], ["-cn"], ["-so", "-tv"]):
        code = run_in_docker(
            ["tlsx", "-u", target] + probe,
            timeout=timeout,
            output=output,
        )
        # Keep the first non-zero exit so failures aren't reported as success.
        if code != 0 and exit_code == 0:
            exit_code = code
    return exit_code


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tool_tlsx.py <target-domain>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
