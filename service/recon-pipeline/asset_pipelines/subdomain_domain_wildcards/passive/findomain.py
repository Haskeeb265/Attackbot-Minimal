"""findomain — passive subdomains from 30+ sources (CT, GitHub, ...)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main


class Findomain(SubdomainTool):
    name = "findomain"
    binary = "findomain"
    category = "passive"
    default_confidence = 0.5

    def command(self, target=None, infile=None):
        # -q keeps output quiet (bare hostnames, no banner).
        return [self.binary, "-t", target, "-q"]


TOOL = Findomain()

if __name__ == "__main__":
    cli_main(TOOL)
