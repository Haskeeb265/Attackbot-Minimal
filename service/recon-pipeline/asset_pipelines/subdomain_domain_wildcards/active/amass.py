"""amass (active) — zone transfers + cert name grabs (`-active`).

Same v4.2.0 graph-relations stdout as passive amass, so it reuses the same
line-scanning parser. Active mode issues DNS queries, so it belongs to the
active stage.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main, in_scope, normalize_host

_HOST_TOKEN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")


class AmassActive(SubdomainTool):
    name = "amass-active"
    binary = "amass"
    category = "active"
    input_mode = "arg"
    timeout = 1200
    default_confidence = 0.7

    def command(self, target=None, infile=None):
        return [self.binary, "enum", "-d", target, "-active", "-timeout", "15"]

    def parse(self, stdout, domain):
        found = set()
        for line in stdout.splitlines():
            for token in _HOST_TOKEN.findall(line):
                host = normalize_host(token)
                if host and in_scope(host, domain):
                    found.add(host)
        return found


TOOL = AmassActive()

if __name__ == "__main__":
    cli_main(TOOL)
