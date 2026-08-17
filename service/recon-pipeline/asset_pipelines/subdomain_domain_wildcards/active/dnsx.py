"""dnsx — fast DNS resolver. Reads a hosts list on stdin, keeps only the names
that resolve, and records their A records for RESOLVES_TO graph edges."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main, in_scope, normalize_host


class Dnsx(SubdomainTool):
    name = "dnsx"
    binary = "dnsx"
    category = "active"
    input_mode = "stdin"
    default_confidence = 0.9

    def command(self, target=None, infile=None):
        # -json emits one object per resolving host: {"host": ..., "a": [...]}.
        return [self.binary, "-silent", "-json", "-a"]

    def parse(self, stdout, domain):
        live = set()
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            host = normalize_host(obj.get("host", ""))
            if not host or (domain and not in_scope(host, domain)):
                continue
            live.add(host)
            ips = [ip for ip in obj.get("a", []) if ip]
            if ips:
                self.resolutions[host] = sorted(set(ips))
        return live


TOOL = Dnsx()

if __name__ == "__main__":
    cli_main(TOOL)
