"""
tools/urls/waybackurls.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
WaybackurlsTool — Wayback Machine URL extraction.

Binary: ``waybackurls``
Stage:  URL_DISCOVERY
Input:  Live subdomain FQDNs (via stdin)
Output: Historical URLs from Wayback Machine
"""

from __future__ import annotations

import logging
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.URL_DISCOVERY)
class WaybackurlsTool(ReconTool):
    """Wayback Machine URL extraction using waybackurls."""

    name    = "WaybackurlsTool"
    binary  = "waybackurls"
    timeout = 600

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        results: List[ReconResult] = []

        for target in targets:
            cmd = [self.binary, target]
            returncode, stdout, stderr = await self._run_subprocess(cmd)

            if returncode != 0:
                log.warning("waybackurls failed for %s: %s", target, stderr.strip())
                results.append(self._make_result(
                    target, data={}, raw_output=stderr,
                    success=False, error=f"waybackurls exited {returncode}",
                ))
                continue

            urls: List[str] = []
            for line in stdout.strip().splitlines():
                url = line.strip()
                if url and url.startswith(("http://", "https://")):
                    urls.append(url)

            urls = sorted(set(urls))

            sd = state.get_subdomain(target)
            if sd:
                for url in urls:
                    if url not in sd.urls:
                        sd.urls.append(url)

            log.info("waybackurls: %s -> %d URLs", target, len(urls))
            results.append(self._make_result(
                target,
                data={"urls": urls[:500], "count": len(urls)},
                raw_output=stdout[:5000],
            ))

        return results

    def is_installed(self) -> bool:
        return self._check_binary()
