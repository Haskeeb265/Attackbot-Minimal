"""
Base class + shared helpers for the subdomain / domain / wildcard recon tools.

Every tool stub in ``passive/``, ``active/`` and ``permutation/`` is a thin
subclass of :class:`SubdomainTool`. The pattern mirrors the scraper's
``shared/connectors/base.py`` (one small ABC-ish base, concrete subclasses per
source) but adapted to command-line tools bundled in the
``subdomain_domain_wildcards_image`` Docker image (see the sibling
``Dockerfile`` / ``commands.txt``).

Design notes
------------
* **Runs inside the image.** Each tool shells out to its binary *by name*
  (``shutil.which``), exactly as the Dockerfile smoke-test does. The Python
  modules are meant to run where those binaries live — inside the container.
* **Not an importable package.** ``service/recon-pipeline/`` contains a hyphen,
  so these files cannot be imported as a dotted module path. Each tool file is a
  self-contained script (``python passive/subfinder.py -d example.com``) and the
  orchestrator (``main.py``) loads them by file path. That is why every tool
  file re-inserts this folder onto ``sys.path`` before ``from base import ...``.
* **Uniform contract.** Whatever the tool, :meth:`SubdomainTool.run` returns a
  ``set[str]`` of in-scope, normalized subdomain FQDNs. Resolvers additionally
  populate :attr:`SubdomainTool.resolutions` (``host -> [ip, ...]``) so the
  orchestrator can write ``RESOLVES_TO`` edges.
* **Never raises.** A missing binary, a missing API key, a timeout or a crash
  is logged (via ``shared.colorlog.log``) and yields an empty set — one broken
  tool never aborts the pipeline.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

# Make the repo root importable so ``shared.colorlog`` resolves regardless of
# the cwd the tool is launched from (mirrors graph/repository.py's sys.path shim).
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.colorlog import log

# massdns ships its resolver list here in the image (see Dockerfile); the
# resolver-based tools default to it.
RESOLVERS_PATH = "/usr/local/share/massdns/resolvers.txt"


# ---------------------------------------------------------------------------
# Normalization helpers (a tiny, local stand-in for the pipeline's future S3
# normalization stage — lowercase, strip scheme/port/path, drop wildcards).
# ---------------------------------------------------------------------------
def normalize_host(raw: str) -> Optional[str]:
    """Reduce a raw tool output token to a canonical hostname, or ``None``.

    Handles the shapes tools actually emit: bare hosts, ``*.example.com``
    wildcards, ``https://host:443/path`` URLs, trailing dots and stray
    whitespace. Returns ``None`` for anything that is not a plausible hostname.
    """
    if not raw:
        return None
    host = raw.strip().lower()
    if not host:
        return None
    # Strip a scheme and everything after the authority (path/query).
    host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", host)
    host = host.split("/", 1)[0]
    host = host.split("@", 1)[-1]        # drop any userinfo
    host = host.split(":", 1)[0]         # drop :port
    host = host.lstrip("*.")             # *.example.com -> example.com
    host = host.rstrip(".")              # fqdn trailing dot
    if not host or " " in host or "." not in host:
        return None
    # A conservative hostname charset; rejects obvious junk lines.
    if not re.fullmatch(r"[a-z0-9._-]+", host):
        return None
    return host


def in_scope(host: str, domain: str) -> bool:
    """True if ``host`` is ``domain`` itself or a subdomain of it."""
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


# ---------------------------------------------------------------------------
# Base tool
# ---------------------------------------------------------------------------
class SubdomainTool:
    """Base class for every subdomain/domain/wildcard tool wrapper.

    Subclasses set the class attributes and implement :meth:`command`. The two
    non-passive input shapes (a hosts list on stdin, or a hosts list written to
    a temp file passed as an argument) are handled here so subclasses only
    describe *how to invoke the binary*.

    Class attributes
    ----------------
    name / binary : str
        Human name and the on-PATH binary name.
    category : str
        ``"passive"`` | ``"active"`` | ``"permutation"`` — drives orchestration.
    input_mode : str
        ``"arg"``   — the root domain is passed as a CLI argument (passive).
        ``"stdin"`` — a newline-joined hosts list is piped to stdin.
        ``"file"``  — a hosts list is written to a temp file passed to
        :meth:`command` as ``infile``.
    api_key_env : Optional[str]
        Name of an env var that must be set for the tool to work (e.g. chaos).
        When absent the tool is skipped with a warning rather than failing.
    default_confidence : float
        Provenance confidence stamped on graph edges for results from this tool.
    """

    name: str = ""
    binary: str = ""
    category: str = "passive"
    input_mode: str = "arg"
    timeout: int = 600
    api_key_env: Optional[str] = None
    default_confidence: float = 0.5

    def __init__(self) -> None:
        # host -> [ip, ...]; only resolvers populate this (see active/dnsx.py).
        self.resolutions: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------
    def command(self, target: Optional[str] = None, infile: Optional[str] = None) -> List[str]:
        """Return the argv list for one invocation. Override in every subclass."""
        raise NotImplementedError

    def parse(self, stdout: str, domain: str) -> Set[str]:
        """Default parser: one hostname per line, normalized + scope-filtered."""
        found: Set[str] = set()
        for line in stdout.splitlines():
            host = normalize_host(line)
            if host and in_scope(host, domain):
                found.add(host)
        return found

    # ------------------------------------------------------------------
    # Shared machinery
    # ------------------------------------------------------------------
    def is_installed(self) -> bool:
        return bool(self.binary) and shutil.which(self.binary) is not None

    def _run_subprocess(self, cmd: Sequence[str], stdin_data: Optional[str] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            list(cmd),
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

    def run(self, domain: Optional[str] = None, hosts: Optional[Sequence[str]] = None) -> Set[str]:
        """Invoke the tool and return a set of in-scope normalized subdomains.

        Never raises: a missing binary/key, timeout or crash is logged and
        yields an empty set. ``domain`` is required for scope filtering (for
        stdin/file tools it is derived from the hosts when not given).
        """
        self.resolutions = {}
        label = self.name or self.__class__.__name__

        if not self.is_installed():
            log.warn(f"{label}: binary '{self.binary}' not found on PATH - skipping")
            return set()

        import os
        if self.api_key_env and not os.getenv(self.api_key_env):
            log.warn(f"{label}: env {self.api_key_env} not set - skipping")
            return set()

        host_list = sorted({h for h in (hosts or []) if h})
        scope_domain = (domain or self._infer_domain(host_list) or "").lower().rstrip(".")

        tmp_path: Optional[str] = None
        stdin_data: Optional[str] = None
        try:
            if self.input_mode == "arg":
                cmd = self.command(target=scope_domain)
            elif self.input_mode == "stdin":
                stdin_data = "\n".join(host_list) + "\n"
                cmd = self.command(target=scope_domain)
            elif self.input_mode == "file":
                fd, tmp_path = tempfile.mkstemp(prefix=f"{self.binary}_", suffix=".txt")
                with os.fdopen(fd, "w") as fh:
                    fh.write("\n".join(host_list) + "\n")
                cmd = self.command(target=scope_domain, infile=tmp_path)
            else:  # pragma: no cover - guarded by class definitions
                raise ValueError(f"unknown input_mode {self.input_mode!r}")

            log.process(f"{label}: {' '.join(cmd)}")
            proc = self._run_subprocess(cmd, stdin_data=stdin_data)
        except subprocess.TimeoutExpired:
            log.failed(f"{label}: timed out after {self.timeout}s")
            return set()
        except (FileNotFoundError, OSError) as exc:
            log.failed(f"{label}: failed to launch ({exc})")
            return set()
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        if proc.returncode != 0 and not proc.stdout.strip():
            log.warn(f"{label}: exit {proc.returncode} — {proc.stderr.strip()[:200]}")
            return set()

        results = self.parse(proc.stdout, scope_domain)
        log.success(f"{label}: {len(results)} subdomains")
        return results

    @staticmethod
    def _infer_domain(hosts: Sequence[str]) -> Optional[str]:
        """Best-effort registrable-ish domain for scope filtering stdin/file input.

        Uses the most common last-two-labels among the input hosts. Good enough
        for the in-scope filter when the caller did not pass an explicit domain.
        """
        counts: Dict[str, int] = {}
        for h in hosts:
            parts = h.split(".")
            if len(parts) >= 2:
                counts[".".join(parts[-2:])] = counts.get(".".join(parts[-2:]), 0) + 1
        return max(counts, key=counts.get) if counts else None


# ---------------------------------------------------------------------------
# Standalone-script entrypoint — lets each tool file run on its own inside the
# image:  python passive/subfinder.py -d example.com
# ---------------------------------------------------------------------------
def cli_main(tool: SubdomainTool) -> None:
    parser = argparse.ArgumentParser(description=f"{tool.name} ({tool.category}) subdomain tool")
    parser.add_argument("-d", "--domain", help="root domain (passive) / scope filter")
    parser.add_argument(
        "-i", "--stdin", action="store_true",
        help="read a hosts list from stdin (for active/permutation tools)",
    )
    args = parser.parse_args()

    hosts: List[str] = []
    if args.stdin or tool.input_mode in ("stdin", "file"):
        hosts = [line.strip() for line in sys.stdin if line.strip()]

    results = tool.run(domain=args.domain, hosts=hosts)
    for host in sorted(results):
        print(host)
