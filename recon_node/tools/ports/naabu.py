"""
tools/ports/naabu.py
~~~~~~~~~~~~~~~~~~~~
NaabuTool — fast port scanning via ProjectDiscovery's naabu.

Binary: ``naabu``
Stage:  PORT_SCAN
Input:  Live host FQDNs/IPs (via stdin)
Output: Open ports per host
"""

from __future__ import annotations

import json
import logging
from typing import List

from recon_node.models import PipelineState, Port, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.PORT_SCAN)
class NaabuTool(ReconTool):
    """Fast SYN/CONNECT port scan using naabu."""

    name    = "NaabuTool"
    binary  = "naabu"
    timeout = 900  # large scope

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
        ]

        returncode, stdout, stderr = await self._run_subprocess(
            cmd, stdin_data=stdin_data,
        )

        if returncode != 0:
            log.warning("naabu failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"naabu exited {returncode}",
            )]

        open_ports: List[dict] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                host = obj.get("host", obj.get("ip", "")).strip().lower()
                port = obj.get("port", 0)
                if host and port:
                    open_ports.append({"host": host, "port": port})
                    sd = state.get_subdomain(host)
                    if sd:
                        existing = {p.port for p in sd.ports}
                        if port not in existing:
                            sd.ports.append(Port(port=port))
            except Exception as exc:
                log.debug("naabu: parse error: %s", exc)

        log.info("naabu: %d open ports across %d hosts", len(open_ports), len(targets))
        return [self._make_result(
            "(batch)",
            data={"open_ports": open_ports, "count": len(open_ports)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
