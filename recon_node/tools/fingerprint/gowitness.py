"""
tools/fingerprint/gowitness.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
GowitnessTool — web screenshot capture via gowitness.

Binary: ``gowitness``
Stage:  FINGERPRINT
Input:  Live subdomain FQDNs (via stdin)
Output: Screenshot paths per host
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import ReconTool, register_tool

log = logging.getLogger(__name__)


@register_tool(stage=Stage.FINGERPRINT)
class GowitnessTool(ReconTool):
    """Web screenshot capture using gowitness."""

    name    = "GowitnessTool"
    binary  = "gowitness"
    timeout = 900

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        if not targets:
            return []

        # Write targets as URLs to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="gowitness_"
        ) as f:
            for t in targets:
                if not t.startswith(("http://", "https://")):
                    f.write(f"https://{t}\n")
                    f.write(f"http://{t}\n")
                else:
                    f.write(t + "\n")
            input_path = f.name

        # Use state's output_dir for screenshots
        screenshot_dir = Path(state.output_dir) / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        try:
            cmd = [
                self.binary, "file",
                "-f", input_path,
                "--screenshot-path", str(screenshot_dir),
            ]
            returncode, stdout, stderr = await self._run_subprocess(cmd)
        finally:
            Path(input_path).unlink(missing_ok=True)

        if returncode != 0:
            log.warning("gowitness failed: %s", stderr.strip())
            return [self._make_result(
                "(batch)", data={}, raw_output=stderr,
                success=False, error=f"gowitness exited {returncode}",
            )]

        # Update state with screenshot paths (best-effort)
        screenshots: List[str] = []
        for sd in state.subdomains:
            if sd.is_live and sd.http_metadata:
                # gowitness saves screenshots named after URL hash
                sd.http_metadata.screenshot_path = str(screenshot_dir)
                screenshots.append(sd.subdomain)

        log.info("gowitness: screenshots for %d hosts", len(screenshots))
        return [self._make_result(
            "(batch)",
            data={"screenshot_dir": str(screenshot_dir),
                  "hosts": screenshots, "count": len(screenshots)},
            raw_output=stdout[:5000],
        )]

    def is_installed(self) -> bool:
        return self._check_binary()
