"""puredns (resolve mode) — mass-resolve a hosts list with wildcard filtering.

Reads the candidate hosts from a temp file and returns the ones that resolve
(wildcards filtered out). Uses the massdns resolver list bundled in the image.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import RESOLVERS_PATH, SubdomainTool, cli_main


class Puredns(SubdomainTool):
    name = "puredns"
    binary = "puredns"
    category = "active"
    input_mode = "file"
    default_confidence = 0.85

    def command(self, target=None, infile=None):
        return [self.binary, "resolve", infile, "-r", RESOLVERS_PATH, "--quiet"]


TOOL = Puredns()

if __name__ == "__main__":
    cli_main(TOOL)
