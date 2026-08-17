"""assetfinder — passive subdomains from cert transparency + web sources."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main


class Assetfinder(SubdomainTool):
    name = "assetfinder"
    binary = "assetfinder"
    category = "passive"
    default_confidence = 0.5

    def command(self, target=None, infile=None):
        # --subs-only keeps the output to subdomains of the target only.
        return [self.binary, "--subs-only", target]


TOOL = Assetfinder()

if __name__ == "__main__":
    cli_main(TOOL)
