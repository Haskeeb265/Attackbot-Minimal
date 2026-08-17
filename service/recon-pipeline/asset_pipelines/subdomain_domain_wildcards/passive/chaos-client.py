"""chaos — ProjectDiscovery Chaos dataset lookup.

The chaos-client binary is named ``chaos`` and reads its key from the
``PDCP_API_KEY`` env var (the repo's ``.env`` stores it as ``CHAOS_API_KEY`` —
export it as ``PDCP_API_KEY`` before running, see commands.txt). Without a key
the tool is skipped rather than failed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main


class Chaos(SubdomainTool):
    name = "chaos"
    binary = "chaos"
    category = "passive"
    api_key_env = "PDCP_API_KEY"
    default_confidence = 0.6

    def command(self, target=None, infile=None):
        return [self.binary, "-d", target, "-silent"]


TOOL = Chaos()

if __name__ == "__main__":
    cli_main(TOOL)
