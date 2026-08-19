"""
tools/ports/nmap_tool.py
~~~~~~~~~~~~~~~~~~~~~~~~~
NmapTool — service version detection via nmap.

Binary: ``nmap``
Stage:  PORT_SCAN
Input:  Live host FQDNs/IPs
Output: Open ports with service/version info
"""

from __future__ import annotations

import logging
import re
from typing import List

from recon_node.models import PipelineState, Port, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.PORT_SCAN)
class NmapTool(ReconTool):
    """Service version detection using nmap -sV."""

    name    = "NmapTool"
    binary  = "nmap"
    timeout = 900

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        results: List[ReconResult] = []

        for target in targets:
            # Grab known ports from state to focus scan
            sd = state.get_subdomain(target)
            port_args = []
            if sd and sd.ports:
                port_args = ["-p", ",".join(str(p.port) for p in sd.ports)]

            cmd = [
                self.binary,
                "-sV",
                "--open",
                "-T4",
                *port_args,
                target,
            ]

            returncode, stdout, stderr = await self._run_subprocess(cmd)

            if returncode != 0:
                log.warning("nmap failed for %s: %s", target, stderr.strip())
                results.append(self._make_result(
                    target, data={}, raw_output=stderr,
                    success=False, error=f"nmap exited {returncode}",
                ))
                continue

            # Parse nmap grep-style output
            # e.g. "80/tcp   open  http    Apache httpd 2.4.52"
            port_pattern = re.compile(
                r"^(\d+)/(\w+)\s+open\s+(\S+)\s*(.*)$", re.MULTILINE
            )

            ports_found: List[dict] = []
            for match in port_pattern.finditer(stdout):
                port_num = int(match.group(1))
                protocol = match.group(2)
                service  = match.group(3)
                version  = match.group(4).strip() or None

                ports_found.append({
                    "port": port_num, "protocol": protocol,
                    "service": service, "version": version,
                })

                if sd:
                    existing = {p.port for p in sd.ports}
                    if port_num in existing:
                        for p in sd.ports:
                            if p.port == port_num:
                                p.service = service
                                p.version = version
                                p.protocol = protocol
                    else:
                        sd.ports.append(Port(
                            port=port_num, protocol=protocol,
                            service=service, version=version,
                        ))

            log.info("nmap: %s -> %d services", target, len(ports_found))
            results.append(self._make_result(
                target,
                data={"ports": ports_found, "count": len(ports_found)},
                raw_output=stdout[:5000],
            ))

        return results

    def is_installed(self) -> bool:
        return self._check_binary()
