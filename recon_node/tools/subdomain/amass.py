"""
tools/subdomain/amass.py
~~~~~~~~~~~~~~~~~~~~~~~~~
AmassTool — active + passive subdomain enumeration via OWASP Amass.

Binary: ``amass``
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
class AmassTool(ReconTool):
    """Subdomain enumeration using OWASP Amass (passive mode)."""

    name    = "AmassTool"
    binary  = "amass"
    timeout = 900  # 15 min — amass can be slow

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        results: List[ReconResult] = []

        for target in targets:
            cmd = [
                self.binary, "enum",
                "-passive",
                "-d", target,
            ]

            returncode, stdout, stderr = await self._run_subprocess(cmd)

            if returncode != 0:
                log.warning("amass failed for %s: %s", target, stderr.strip())
                results.append(self._make_result(
                    target, data={}, raw_output=stderr,
                    success=False, error=f"amass exited {returncode}",
                ))
                continue

            subdomains: List[str] = []
            for line in stdout.strip().splitlines():
                fqdn = line.strip().lower()
                if fqdn and "." in fqdn and " " not in fqdn:
                    subdomains.append(fqdn)

            subdomains = sorted(set(subdomains))
            for fqdn in subdomains:
                state.upsert_subdomain(Subdomain(subdomain=fqdn, source=self.tool_name))

            log.info("amass: %s -> %d subdomains", target, len(subdomains))
            results.append(self._make_result(
                target,
                data={"subdomains": subdomains, "count": len(subdomains)},
                raw_output=stdout[:5000],
            ))

        return results

    def is_installed(self) -> bool:
        return self._check_binary()
