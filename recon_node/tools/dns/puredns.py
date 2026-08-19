"""
tools/dns/puredns.py
~~~~~~~~~~~~~~~~~~~~
PurednsTool — DNS resolution and wildcard filtering via puredns.

Binary: ``puredns``
Stage:  DNS_RESOLUTION
Input:  Subdomain FQDNs
Output: Resolved subdomains with IP addresses
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.DNS_RESOLUTION)
class PurednsTool(ReconTool):
    """DNS resolution and wildcard filtering using puredns."""

    name    = "PurednsTool"
    binary  = "puredns"
    timeout = 600

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        if not targets:
            return []

        # Write targets to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="puredns_in_"
        ) as f:
            for t in targets:
                f.write(t + "\n")
            input_path = f.name

        try:
            cmd = [
                self.binary, "resolve",
                input_path,
                "--quiet",
            ]
            returncode, stdout, stderr = await self._run_subprocess(cmd)
        finally:
            Path(input_path).unlink(missing_ok=True)

        if returncode != 0:
            log.warning("puredns failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"puredns exited {returncode}",
            )]

        resolved: List[str] = []
        for line in stdout.strip().splitlines():
            fqdn = line.strip().lower()
            if fqdn and "." in fqdn:
                resolved.append(fqdn)

        resolved = sorted(set(resolved))

        # Mark resolved subdomains in state
        for fqdn in resolved:
            sd = state.get_subdomain(fqdn)
            if sd:
                sd.ip_addresses = sd.ip_addresses or ["resolved"]

        log.info("puredns: %d/%d resolved (wildcards filtered)", len(resolved), len(targets))
        return [self._make_result(
            "(batch)",
            data={"resolved": resolved, "count": len(resolved),
                  "total_input": len(targets)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
