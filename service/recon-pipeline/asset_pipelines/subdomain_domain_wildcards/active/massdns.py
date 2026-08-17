"""massdns — high-speed bulk DNS resolution.

Reads the candidate hosts from a temp file, resolves them against the bundled
resolver list, and returns the names that answered (capturing A records for
RESOLVES_TO edges). ``-o S`` is massdns' simple output:

    sub.example.com. A 93.184.216.34
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import RESOLVERS_PATH, SubdomainTool, cli_main, in_scope, normalize_host


class Massdns(SubdomainTool):
    name = "massdns"
    binary = "massdns"
    category = "active"
    input_mode = "file"
    default_confidence = 0.8

    def command(self, target=None, infile=None):
        # -w /dev/stdout streams the simple ("S") output back to us.
        return [self.binary, "-r", RESOLVERS_PATH, "-t", "A", "-o", "S", "-w", "/dev/stdout", infile]

    def parse(self, stdout, domain):
        live = set()
        for line in stdout.splitlines():
            parts = line.split()
            if len(parts) < 3 or parts[1] not in ("A", "AAAA"):
                continue
            host = normalize_host(parts[0])
            if not host or (domain and not in_scope(host, domain)):
                continue
            live.add(host)
            self.resolutions.setdefault(host, [])
            if parts[2] not in self.resolutions[host]:
                self.resolutions[host].append(parts[2])
        return live


TOOL = Massdns()

if __name__ == "__main__":
    cli_main(TOOL)
