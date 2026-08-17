"""gotator — deeper subdomain permutations than dnsgen (word splicing, numbers,
depth). Reads the known-names list from a temp file, reusing it as the
permutation wordlist too."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import SubdomainTool, cli_main


class Gotator(SubdomainTool):
    name = "gotator"
    binary = "gotator"
    category = "permutation"
    input_mode = "file"
    default_confidence = 0.3

    def command(self, target=None, infile=None):
        # -sub known names, -perm token source (reuse the same list). -depth 1
        # / -numbers 3 bound the blow-up; -mindup drops repeats, -adl adds
        # per-level permutations.
        return [
            self.binary, "-sub", infile, "-perm", infile,
            "-depth", "1", "-numbers", "3", "-mindup", "-adl", "-silent",
        ]


TOOL = Gotator()

if __name__ == "__main__":
    cli_main(TOOL)
