"""shuffledns (resolve mode) — massdns wrapper that resolves a hosts list and
filters wildcards. Brute-force mode (needs a wordlist) is a separate concern;
here shuffledns is used purely as a resolver over already-discovered names."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> pipeline root (base.py)
from base import RESOLVERS_PATH, SubdomainTool, cli_main


class Shuffledns(SubdomainTool):
    name = "shuffledns"
    binary = "shuffledns"
    category = "active"
    input_mode = "file"
    default_confidence = 0.85

    def command(self, target=None, infile=None):
        return [
            self.binary, "-d", target, "-list", infile,
            "-r", RESOLVERS_PATH, "-mode", "resolve", "-silent",
        ]


TOOL = Shuffledns()

if __name__ == "__main__":
    cli_main(TOOL)
