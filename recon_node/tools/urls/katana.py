"""
tools/urls/katana.py
~~~~~~~~~~~~~~~~~~~~
KatanaTool — modern web crawler via ProjectDiscovery's katana.

Binary: ``katana``
Stage:  URL_DISCOVERY
Input:  Live subdomain FQDNs (via stdin)
Output: Crawled URLs (JS parsed, form actions, API endpoints)
"""

from __future__ import annotations

import logging
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.URL_DISCOVERY)
class KatanaTool(ReconTool):
    """Modern web crawling using katana."""

    name    = "KatanaTool"
    binary  = "katana"
    timeout = 600

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        if not targets:
            return []

        stdin_data = "\n".join(targets).encode("utf-8")
        cmd = [
            self.binary,
            "-silent",
            "-jc",       # JavaScript crawling
            "-d", "3",   # depth 3
            "-ct", "5",  # concurrency
        ]

        returncode, stdout, stderr = await self._run_subprocess(
            cmd, stdin_data=stdin_data,
        )

        if returncode != 0:
            log.warning("katana failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"katana exited {returncode}",
            )]

        urls: List[str] = []
        for line in stdout.strip().splitlines():
            url = line.strip()
            if url and url.startswith(("http://", "https://")):
                urls.append(url)

        urls = sorted(set(urls))

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

        log.info("katana: %d unique URLs crawled", len(urls))
        return [self._make_result(
            "(batch)",
            data={"urls": urls[:500], "count": len(urls)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
