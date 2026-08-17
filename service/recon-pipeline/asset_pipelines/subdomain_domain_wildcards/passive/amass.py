"""amass (passive) — CT logs + OSINT; v4.2.0 streams graph relations to stdout.

The image pins amass v4.2.0, which prints one relation per line, e.g.:

    sub.example.com (FQDN) --> a_record --> 104.21.81.2 (IPAddress)
    sub.example.com (FQDN) --> cname_record --> other.example.com (FQDN)

so the default one-host-per-line parser will not do — we scan every line for
in-scope FQDN tokens instead.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main, in_scope, normalize_host

_HOST_TOKEN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")


class AmassPassive(SubdomainTool):
    name = "amass"
    binary = "amass"
    category = "passive"
    timeout = 1200  # amass is slow; sources take minutes to warm up
    default_confidence = 0.6

    def command(self, target=None, infile=None):
        # Passive is the default mode; -timeout is in MINUTES for amass.
        return [self.binary, "enum", "-d", target, "-timeout", "15"]

    def parse(self, stdout, domain):
        found = set()
        for line in stdout.splitlines():
            for token in _HOST_TOKEN.findall(line):
                host = normalize_host(token)
                if host and in_scope(host, domain):
                    found.add(host)
        return found


TOOL = AmassPassive()

if __name__ == "__main__":
    cli_main(TOOL)
