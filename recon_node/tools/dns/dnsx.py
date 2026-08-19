"""
tools/dns/dnsx.py
~~~~~~~~~~~~~~~~~
DnsxTool — DNS probing and record retrieval via dnsx.

Binary: ``dnsx``
Stage:  DNS_RESOLUTION
Input:  Subdomain FQDNs (via stdin)
Output: Resolved subdomains with A/AAAA/CNAME records
"""

from __future__ import annotations

import json
import logging
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.DNS_RESOLUTION)
class DnsxTool(ReconTool):
    """DNS resolution and record extraction using dnsx."""

    name    = "DnsxTool"
    binary  = "dnsx"
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
            "-a", "-aaaa", "-cname",
            "-resp",
            "-json",
        ]

        returncode, stdout, stderr = await self._run_subprocess(
            cmd, stdin_data=stdin_data,
        )

        if returncode != 0:
            log.warning("dnsx failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"dnsx exited {returncode}",
            )]

        resolved_hosts: List[dict] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                host = obj.get("host", "").strip().lower()
                a_records = obj.get("a", [])
                aaaa_records = obj.get("aaaa", [])
                cname_records = obj.get("cname", [])

                if host:
                    resolved_hosts.append({
                        "host": host,
                        "a": a_records,
                        "aaaa": aaaa_records,
                        "cname": cname_records,
                    })
                    # Update state
                    sd = state.get_subdomain(host)
                    if sd:
                        sd.ip_addresses = list(set(
                            sd.ip_addresses + a_records + aaaa_records
                        ))
            except Exception as exc:
                log.debug("dnsx: failed to parse line %r: %s", line, exc)

        log.info("dnsx: %d/%d hosts resolved", len(resolved_hosts), len(targets))
        return [self._make_result(
            "(batch)",
            data={"resolved": resolved_hosts, "count": len(resolved_hosts)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
