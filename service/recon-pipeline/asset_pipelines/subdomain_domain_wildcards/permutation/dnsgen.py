"""dnsgen — generate candidate subdomains by permuting known names (stdin)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main


class Dnsgen(SubdomainTool):
    name = "dnsgen"
    binary = "dnsgen"
    category = "permutation"
    input_mode = "stdin"
    default_confidence = 0.3

    def command(self, target=None, infile=None):
        return [self.binary, "-"]  # read the known-names list from stdin


TOOL = Dnsgen()

if __name__ == "__main__":
    cli_main(TOOL)
