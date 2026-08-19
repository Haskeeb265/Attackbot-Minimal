"""
pipeline/state.py
~~~~~~~~~~~~~~~~~
StateManager — checkpoint persistence and resume logic.

Every time a pipeline stage completes, the PipelineState is serialized to
disk so that a crashed or interrupted run can be resumed exactly where it
left off.

CONTRACT
--------
save(state, output_dir)
    Serialize ``state`` to JSON at a deterministic path inside ``output_dir``.
    Write is atomic: JSON is written to a ``.tmp`` file first, then renamed
    into place so no consumer ever sees a partial write.
    Creates ``output_dir / target /`` if it does not exist.
    Returns the Path of the written file.

load(output_dir, target, run_id=None)
    Deserialize the checkpoint for ``target`` back into a PipelineState.
    Returns ``None`` if no checkpoint exists or the file is corrupt.
    NEVER raises — all errors are caught and logged.
    If ``run_id`` is supplied, validates that the loaded checkpoint's
    run_id matches; returns None on mismatch.

can_resume(output_dir, target)
    Returns True iff a valid, readable checkpoint exists for ``target``.

checkpoint_path(output_dir, target)
    Returns the canonical Path for the checkpoint file (may not exist yet).

new_state(target, scope, output_dir, run_id=None)
    Factory that creates a fresh PipelineState with a UUID run_id and
    the correct output_dir.  Use this instead of constructing PipelineState
    directly in the pipeline runner.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from recon_node.models import PipelineState, Stage

log = logging.getLogger(__name__)

# Bump this when PipelineState schema changes in a breaking way
CHECKPOINT_SCHEMA_VERSION = 1


class StateManager:
    """
    Manages checkpoint persistence for a pipeline run.

    This class is stateless beyond its constructor arguments — it does not
    cache the PipelineState it writes.  All path computation is pure and
    deterministic.

    Parameters
    ----------
    output_dir:
        Root output directory (e.g. ``"./output"`` or ``"/tmp/recon"``).
        Sub-directories per target are created automatically.
    """

    CHECKPOINT_FILENAME = "checkpoint.json"

    def __init__(self, output_dir: str = "./output") -> None:
        self._output_dir = Path(output_dir).resolve()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def checkpoint_path(self, target: str) -> Path:
        """
        Return the canonical path for ``target``'s checkpoint file.

        Path: ``<output_dir>/<target>/checkpoint.json``

        The file may not yet exist — this is a pure path computation.
        """
        return self._output_dir / self._sanitize_target(target) / self.CHECKPOINT_FILENAME

    def target_dir(self, target: str) -> Path:
        """Return the per-target output directory, creating it if needed."""
        d = self._output_dir / self._sanitize_target(target)
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def save(self, state: PipelineState) -> Path:
        """
        Atomically serialize ``state`` to disk.

        Steps:
        1. Render to JSON using Pydantic's serializer (handles datetime, enums, etc.).
        2. Wrap in a versioned envelope ``{schema_version, saved_at, state}``.
        3. Write to ``<checkpoint_path>.tmp``.
        4. ``os.replace()`` (atomic on all major OSes) renames tmp → final.

        Returns
        -------
        Path
            The path of the written checkpoint file.

        Raises
        ------
        OSError
            If the file cannot be written (e.g. disk full, permission denied).
            This is intentionally NOT caught — a failed checkpoint write is a
            hard error; the caller (StageRunner) should log and abort.
        """
        dest = self.checkpoint_path(state.target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp  = dest.with_suffix(".tmp")

        envelope = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "saved_at":       datetime.now(timezone.utc).isoformat(),
            "state":          json.loads(state.model_dump_json()),
        }

        tmp.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, dest)   # atomic on Windows (NTFS) and POSIX

        log.info(
            "Checkpoint saved: target=%s completed_stages=%s path=%s",
            state.target,
            [s.value for s in state.completed_stages],
            dest,
        )
        return dest

    def load(
        self,
        target: str,
        run_id: Optional[str] = None,
    ) -> Optional[PipelineState]:
        """
        Deserialize a checkpoint for ``target``.

        Returns
        -------
        PipelineState | None
            The deserialized state, or None if:
            - No checkpoint file exists.
            - The file is corrupt / unparseable.
            - Schema version mismatch.
            - ``run_id`` was supplied and does not match the checkpoint.

        NEVER raises.
        """
        path = self.checkpoint_path(target)

        if not path.exists():
            log.debug("No checkpoint found at %s", path)
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            envelope = json.loads(raw)
        except Exception as exc:
            log.warning("Checkpoint at %s is unreadable: %s", path, exc)
            return None

        # Schema version guard
        schema_ver = envelope.get("schema_version")
        if schema_ver != CHECKPOINT_SCHEMA_VERSION:
            log.warning(
                "Checkpoint schema version mismatch (got %s, expected %s) — ignoring",
                schema_ver, CHECKPOINT_SCHEMA_VERSION,
            )
            return None

        state_dict = envelope.get("state")
        if not isinstance(state_dict, dict):
            log.warning("Checkpoint at %s has no 'state' key — ignoring", path)
            return None

        try:
            state = PipelineState.model_validate(state_dict)
        except Exception as exc:
            log.warning("Failed to deserialize checkpoint at %s: %s", path, exc)
            return None

        # Optional run_id validation
        if run_id is not None and state.run_id != run_id:
            log.warning(
                "Checkpoint run_id mismatch (got %s, expected %s) — ignoring",
                state.run_id, run_id,
            )
            return None

        log.info(
            "Checkpoint loaded: target=%s run_id=%s completed_stages=%s",
            state.target,
            state.run_id,
            [s.value for s in state.completed_stages],
        )
        return state

    def can_resume(self, target: str) -> bool:
        """
        Return True iff a valid, readable checkpoint exists for ``target``.

        This is a lightweight check — it attempts a full load and discards
        the result, so the caller doesn't need to call both.
        """
        return self.load(target) is not None

    def delete(self, target: str) -> bool:
        """
        Remove the checkpoint for ``target`` (e.g. after a successful run).

        Returns True if a file was deleted, False if none existed.
        NEVER raises.
        """
        path = self.checkpoint_path(target)
        try:
            path.unlink(missing_ok=True)
            log.info("Checkpoint deleted: %s", path)
            return True
        except Exception as exc:
            log.warning("Failed to delete checkpoint %s: %s", path, exc)
            return False

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def new_state(
        self,
        target: str,
        scope: list[str],
        run_id: Optional[str] = None,
    ) -> PipelineState:
        """
        Create a fresh PipelineState wired to this StateManager's output_dir.

        Parameters
        ----------
        target:
            Root domain being scanned.
        scope:
            In-scope patterns list.
        run_id:
            Optional UUID string; generated automatically if omitted.

        Returns
        -------
        PipelineState
            A clean state ready for the first pipeline stage.
        """
        return PipelineState(
            run_id=run_id or str(uuid.uuid4()),
            target=target,
            scope=scope,
            output_dir=str(self._output_dir),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_target(target: str) -> str:
        """
        Convert a target to a filesystem-safe directory name.

        Strips schemes/ports, replaces characters illegal on Windows/POSIX
        (``< > : " / \\ | ? *``) with underscores.
        """
        # Strip common URL elements
        target = target.strip().lower()
        for prefix in ("https://", "http://"):
            if target.startswith(prefix):
                target = target[len(prefix):]
        target = target.split("/")[0]   # remove path
        target = target.split(":")[0]   # remove port

        # Replace filesystem-unsafe characters
        safe = ""
        for ch in target:
            if ch in r'<>:"/\\|?*':
                safe += "_"
            else:
                safe += ch
        return safe or "unknown"
