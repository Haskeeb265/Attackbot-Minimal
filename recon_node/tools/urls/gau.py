"""
tools/urls/gau.py
~~~~~~~~~~~~~~~~~
GauTool — historical URL harvesting via gau (GetAllUrls).

Binary: ``gau``
Stage:  URL_DISCOVERY
Input:  Live subdomain FQDNs (via stdin)
Output: Historical URLs for each host
"""

from __future__ import annotations

import logging
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.URL_DISCOVERY)
class GauTool(ReconTool):
    """Historical URL discovery using gau."""

    name    = "GauTool"
    binary  = "gau"
    timeout = 600

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        if not targets:
            return []

        stdin_data = "\n".join(targets).encode("utf-8")
        cmd = [self.binary, "--threads", "5"]

        returncode, stdout, stderr = await self._run_subprocess(
            cmd, stdin_data=stdin_data,
        )

        if returncode != 0:
            log.warning("gau failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"gau exited {returncode}",
            )]

        urls: List[str] = []
        for line in stdout.strip().splitlines():
            url = line.strip()
            if url and url.startswith(("http://", "https://")):
                urls.append(url)

        urls = sorted(set(urls))

        # Assign URLs to subdomains in state
        from urllib.parse import urlparse
        for url in urls:
            try:
                host = urlparse(url).hostname
                if host:
                    sd = state.get_subdomain(host)
                    if sd and url not in sd.urls:
                        sd.urls.append(url)
            except Exception:
                pass

        log.info("gau: %d unique URLs", len(urls))
        return [self._make_result(
            "(batch)",
            data={"urls": urls[:500], "count": len(urls)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
