"""subfinder — passive subdomain enumeration (30+ OSINT sources)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main


class Subfinder(SubdomainTool):
    name = "subfinder"
    binary = "subfinder"
    category = "passive"
    default_confidence = 0.7

    def command(self, target=None, infile=None):
        return [self.binary, "-d", target, "-silent"]


TOOL = Subfinder()

if __name__ == "__main__":
    cli_main(TOOL)
