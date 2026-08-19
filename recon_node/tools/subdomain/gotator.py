"""
tools/subdomain/gotator.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
GotatorTool — subdomain permutation generation via gotator.

Binary: ``gotator``
Stage:  SUBDOMAIN_ENUM
Input:  Root domain(s) — reads existing subdomains from state, generates permutations
Output: Permuted subdomain FQDNs
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage, Subdomain
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.SUBDOMAIN_ENUM)
class GotatorTool(ReconTool):
    """Subdomain permutation using gotator.

    This tool reads existing subdomains from PipelineState (discovered by
    prior tools in the same stage) and feeds them to gotator for permutation.
    If no subdomains exist yet, it uses the root target directly.
    """

    name    = "GotatorTool"
    binary  = "gotator"
    timeout = 600

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        results: List[ReconResult] = []

        # Collect known subdomains from state
        known = [sd.subdomain for sd in state.subdomains] or targets

        for target in targets:
            # Write known subs to a temp file for gotator
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, prefix="gotator_"
            ) as f:
                for sub in known:
                    f.write(sub + "\n")
                input_path = f.name

            try:
                cmd = [
                    self.binary,
                    "-sub", input_path,
                    "-perm", input_path,
                    "-depth", "1",
                    "-numbers", "3",
                    "-mindup",
                    "-adl",
                ]
                returncode, stdout, stderr = await self._run_subprocess(cmd)
            finally:
                Path(input_path).unlink(missing_ok=True)

            if returncode != 0:
                log.warning("gotator failed for %s: %s", target, stderr.strip())
                results.append(self._make_result(
                    target, data={}, raw_output=stderr,
                    success=False, error=f"gotator exited {returncode}",
                ))
                continue

            permutations: List[str] = []
            for line in stdout.strip().splitlines():
                fqdn = line.strip().lower()
                if fqdn and "." in fqdn:
                    permutations.append(fqdn)

            permutations = sorted(set(permutations))
            for fqdn in permutations:
                state.upsert_subdomain(Subdomain(subdomain=fqdn, source=self.tool_name))

            log.info("gotator: %s -> %d permutations", target, len(permutations))
            results.append(self._make_result(
                target,
                data={"permutations": permutations, "count": len(permutations)},
                raw_output=stdout[:5000],
            ))

        return results

    def is_installed(self) -> bool:
        return self._check_binary()
