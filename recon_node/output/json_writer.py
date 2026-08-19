"""
output/json_writer.py
~~~~~~~~~~~~~~~~~~~~~
JsonWriter — writes pipeline output to structured JSON files.

CONTRACT
--------
JsonWriter(output_dir)
    ``output_dir`` — root output directory.  Per-target subdirectories are
    created automatically.

write(state) -> dict[str, Path]
    Write all output artefacts for a completed pipeline run.
    Returns a dict of logical name → file path written.

    Files produced:
    1. ``subdomains.json``   — full list of Subdomain objects
    2. ``live_hosts.json``   — only live subdomains (is_live=True)
    3. ``urls.json``         — all discovered URLs keyed by host
    4. ``ports.json``        — all open ports keyed by host
    5. ``summary.json``      — pipeline run summary (state.summary())
    6. ``full_state.json``   — complete PipelineState for debugging / replay

    All writes are atomic: write to .tmp then os.replace().
    All files are UTF-8 encoded with indent=2 for readability.
    NEVER raises — I/O errors are caught, logged, and the dict entry is omitted.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from recon_node.models import PipelineState

log = logging.getLogger(__name__)


class JsonWriter:
    """
    Writes structured JSON output files for a completed pipeline run.

    Parameters
    ----------
    output_dir:
        Root output directory.  A sub-directory per target is created
        automatically.
    """

    def __init__(self, output_dir: str = "./output") -> None:
        self._output_dir = Path(output_dir).resolve()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, state: PipelineState) -> Dict[str, Path]:
        """
        Write all output artefacts and return a map of name → path.

        Any individual file that fails to write is logged and skipped;
        the rest are still written.
        """
        target_dir = self._target_dir(state.target)
        written: Dict[str, Path] = {}

        # 1. subdomains.json
        self._safe_write(
            target_dir / "subdomains.json",
            [json.loads(sd.model_dump_json()) for sd in state.subdomains],
            written, "subdomains",
        )

        # 2. live_hosts.json
        self._safe_write(
            target_dir / "live_hosts.json",
            [json.loads(sd.model_dump_json()) for sd in state.live_subdomains()],
            written, "live_hosts",
        )

        # 3. urls.json — keyed by host
        urls_by_host: Dict[str, list] = {}
        for sd in state.subdomains:
            if sd.urls:
                urls_by_host[sd.subdomain] = sd.urls
        self._safe_write(
            target_dir / "urls.json",
            urls_by_host,
            written, "urls",
        )

        # 4. ports.json — keyed by host
        ports_by_host: Dict[str, list] = {}
        for sd in state.subdomains:
            if sd.ports:
                ports_by_host[sd.subdomain] = [
                    json.loads(p.model_dump_json()) for p in sd.ports
                ]
        self._safe_write(
            target_dir / "ports.json",
            ports_by_host,
            written, "ports",
        )

        # 5. summary.json
        self._safe_write(
            target_dir / "summary.json",
            state.summary(),
            written, "summary",
        )

        # 6. full_state.json
        self._safe_write(
            target_dir / "full_state.json",
            json.loads(state.model_dump_json()),
            written, "full_state",
        )

        log.info(
            "JsonWriter: wrote %d files to %s", len(written), target_dir
        )
        return written

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _target_dir(self, target: str) -> Path:
        """Return per-target output directory, creating it if needed."""
        safe = self._sanitize(target)
        d = self._output_dir / safe
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _safe_write(
        self,
        path:    Path,
        data:    Any,
        written: Dict[str, Path],
        name:    str,
    ) -> None:
        """Atomically write JSON data to path. On failure, log and skip."""
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            os.replace(tmp, path)
            written[name] = path
        except Exception as exc:
            log.error("JsonWriter: failed to write %s: %s", path, exc)

    @staticmethod
    def _sanitize(target: str) -> str:
        """Make target safe for use as a directory name."""
        target = target.strip().lower()
        for prefix in ("https://", "http://"):
            if target.startswith(prefix):
                target = target[len(prefix):]
        target = target.split("/")[0].split(":")[0]
        safe = ""
        for ch in target:
            if ch in r'<>:"/\|?*':
                safe += "_"
            else:
                safe += ch
        return safe or "unknown"
