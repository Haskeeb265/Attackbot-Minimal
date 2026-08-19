"""
tools/subdomain/subfinder.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SubfinderTool — passive subdomain enumeration via ProjectDiscovery's subfinder.

Binary: ``subfinder``
Stage:  SUBDOMAIN_ENUM
Input:  Root domain(s)
Output: Discovered subdomain FQDNs
"""

from __future__ import annotations

import logging
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage, Subdomain
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.SUBDOMAIN_ENUM)
class SubfinderTool(ReconTool):
    """Passive subdomain discovery using subfinder."""

    name    = "SubfinderTool"
    binary  = "subfinder"
    timeout = 600  # 10 minutes — large scopes need more time

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        results: List[ReconResult] = []

        for target in targets:
            cmd = [
                self.binary,
                "-d", target,
                "-silent",
                "-all",
                "-json",  # JSONL output: one {"host":"..."} per line
            ]

            returncode, stdout, stderr = await self._run_subprocess(cmd)

            if returncode != 0:
                log.warning("subfinder failed for %s: %s", target, stderr.strip())
                results.append(self._make_result(
                    target, data={}, raw_output=stderr,
                    success=False, error=f"subfinder exited {returncode}: {stderr[:200]}",
                ))
                continue

            # Parse JSONL output
            subdomains: List[str] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    import json
                    obj = json.loads(line)
                    host = obj.get("host", "").strip().lower()
                    if host:
                        subdomains.append(host)
                except Exception:
                    # Fallback: treat line as plain subdomain
                    if "." in line and " " not in line:
                        subdomains.append(line.strip().lower())

            # Deduplicate
            subdomains = sorted(set(subdomains))

            # Upsert into state
            for fqdn in subdomains:
                state.upsert_subdomain(Subdomain(
                    subdomain=fqdn,
                    source=self.tool_name,
                ))

            log.info("subfinder: %s -> %d subdomains", target, len(subdomains))
            results.append(self._make_result(
                target,
                data={"subdomains": subdomains, "count": len(subdomains)},
                raw_output=stdout[:5000],
            ))

        return results

    def is_installed(self) -> bool:
        return self._check_binary()
