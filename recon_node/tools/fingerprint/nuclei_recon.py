"""
tools/fingerprint/nuclei_recon.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
NucleiReconTool — technology fingerprinting via nuclei (recon templates only).

Binary: ``nuclei``
Stage:  FINGERPRINT
Input:  Live subdomain FQDNs (via stdin)
Output: Technology/info detections
"""

from __future__ import annotations

import json
import logging
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.FINGERPRINT)
class NucleiReconTool(ReconTool):
    """Technology fingerprinting using nuclei (info-severity templates)."""

    name    = "NucleiReconTool"
    binary  = "nuclei"
    timeout = 900

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        if not targets:
            return []

        stdin_data = "\n".join(
            t if t.startswith(("http://", "https://")) else f"https://{t}"
            for t in targets
        ).encode("utf-8")

        cmd = [
            self.binary,
            "-silent",
            "-jsonl",
            "-severity", "info",
            "-type", "http",
            "-tags", "tech",
            "-rate-limit", "50",
        ]

        returncode, stdout, stderr = await self._run_subprocess(
            cmd, stdin_data=stdin_data,
        )

        if returncode != 0:
            log.warning("nuclei failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"nuclei exited {returncode}",
            )]

        findings: List[dict] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                host  = obj.get("host", "").strip().lower()
                tname = obj.get("template-id", obj.get("templateID", ""))
                name  = obj.get("info", {}).get("name", tname)
                severity = obj.get("info", {}).get("severity", "info")

                if host and name:
                    findings.append({"host": host, "template": tname,
                                     "name": name, "severity": severity})

                    # Add detected tech to subdomain
                    from urllib.parse import urlparse
                    hostname = urlparse(host).hostname or host
                    sd = state.get_subdomain(hostname)
                    if sd and name not in sd.technologies:
                        sd.technologies.append(name)

            except Exception as exc:
                log.debug("nuclei: parse error: %s", exc)

        log.info("nuclei: %d findings", len(findings))
        return [self._make_result(
            "(batch)",
            data={"findings": findings, "count": len(findings)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
