"""
tools/http/httpx_tool.py
~~~~~~~~~~~~~~~~~~~~~~~~~
HttpxTool — HTTP probing and tech detection via ProjectDiscovery's httpx.

Binary: ``httpx``
Stage:  HTTP_PROBE
Input:  Subdomain FQDNs (via stdin)
Output: Live hosts with HTTP metadata (status, title, tech, CDN, etc.)
"""

from __future__ import annotations

import json
import logging
from typing import List

from recon_node.models import HttpMetadata, PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.HTTP_PROBE)
class HttpxTool(ReconTool):
    """HTTP probing and technology detection using httpx."""

    name    = "HttpxTool"
    binary  = "httpx"
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
            "-json",
            "-status-code",
            "-title",
            "-tech-detect",
            "-cdn",
            "-server",
            "-follow-redirects",
            "-content-length",
        ]

        returncode, stdout, stderr = await self._run_subprocess(
            cmd, stdin_data=stdin_data,
        )

        if returncode != 0:
            log.warning("httpx failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"httpx exited {returncode}",
            )]

        probed: List[dict] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                url        = obj.get("url", "")
                host       = obj.get("host", obj.get("input", "")).strip().lower()
                status     = obj.get("status_code") or obj.get("status-code", 0)
                title      = obj.get("title", "")
                techs      = obj.get("tech", [])
                cdn        = obj.get("cdn", False)
                cdn_name   = obj.get("cdn_name", None)
                server     = obj.get("webserver", obj.get("server", ""))
                cl         = obj.get("content_length", obj.get("content-length"))
                ip_addr    = obj.get("a", [None])[0] if isinstance(obj.get("a"), list) else obj.get("host_ip")

                if not host:
                    continue

                probed.append({"host": host, "url": url, "status": status})

                # Update state
                sd = state.get_subdomain(host)
                if sd:
                    sd.is_live = True
                    sd.http_metadata = HttpMetadata(
                        url=url or f"https://{host}",
                        status_code=int(status) if status else 0,
                        title=title or None,
                        technologies=techs if isinstance(techs, list) else [],
                        is_cdn=bool(cdn),
                        cdn_name=cdn_name,
                        server=server or None,
                        content_length=int(cl) if cl else None,
                        ip_address=ip_addr,
                    )
                    if ip_addr and ip_addr not in sd.ip_addresses:
                        sd.ip_addresses.append(ip_addr)

            except Exception as exc:
                log.debug("httpx: failed to parse line: %s", exc)

        log.info("httpx: %d/%d hosts live", len(probed), len(targets))
        return [self._make_result(
            "(batch)",
            data={"live_hosts": probed, "count": len(probed)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
