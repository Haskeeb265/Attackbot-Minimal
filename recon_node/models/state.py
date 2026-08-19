"""
models/state.py
~~~~~~~~~~~~~~~
PipelineState — the single source of truth that flows through all stages.

Every stage reads from and writes back to this object. It is the data bus
of the entire pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .result import ReconResult, Stage, Subdomain


class StageStats(BaseModel):
    """Lightweight statistics captured when a stage finishes."""

    stage:           Stage             = Field(..., description="The stage these stats belong to")
    started_at:      datetime          = Field(..., description="UTC timestamp when the stage began")
    completed_at:    Optional[datetime]= Field(default=None, description="UTC timestamp when the stage ended")
    tools_run:       List[str]         = Field(default_factory=list,
                                              description="Names of tools that were executed")
    tools_failed:    List[str]         = Field(default_factory=list,
                                              description="Names of tools that ran but returned errors")
    tools_skipped:   List[str]         = Field(default_factory=list,
                                              description="Names of tools skipped (not installed)")
    items_in:        int               = Field(default=0, description="Number of targets fed into this stage")
    items_out:       int               = Field(default=0, description="Number of results produced by this stage")
    items_scoped_out:int               = Field(default=0,
                                              description="Targets dropped by ScopeValidator at this stage")

    model_config = {"frozen": False}

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()


class PipelineState(BaseModel):
    """
    Central state object passed through the entire pipeline.

    Lifecycle
    ---------
    1. Created by ``PipelineRunner`` before any stage runs.
    2. Passed to every ``StageRunner`` and every ``ReconTool.run()``.
    3. Written to disk after each stage completes (checkpoint).
    4. Deserialized from disk when ``--resume`` is requested.

    Thread / Asyncio Safety
    -----------------------
    ``StageRunner`` acquires an ``asyncio.Lock`` before mutating shared lists
    (``subdomains``, ``stage_results``).  Do not mutate those fields from
    multiple coroutines without the lock.
    """

    # Identity ---------------------------------------------------------------
    run_id:    str      = Field(..., description="Unique identifier for this pipeline run (UUID4)")
    target:    str      = Field(..., description="Root domain being scanned (e.g. 'example.com')")
    scope:     List[str]= Field(..., description="In-scope patterns (e.g. ['*.example.com', 'api.example.com'])")

    # Runtime paths ----------------------------------------------------------
    output_dir: str     = Field(default="./output",
                                description="Base directory for all output artifacts")

    # Core data accumulators -------------------------------------------------
    subdomains:     List[Subdomain]                    = Field(
                        default_factory=list,
                        description="All discovered subdomains, enriched progressively",
                    )
    stage_results:  Dict[str, List[ReconResult]]       = Field(
                        default_factory=dict,
                        description="Raw ReconResult objects keyed by Stage value string",
                    )

    # Execution tracking -----------------------------------------------------
    started_at:         datetime        = Field(
                            default_factory=lambda: datetime.now(timezone.utc),
                            description="UTC timestamp when this pipeline run started",
                        )
    completed_at:       Optional[datetime] = Field(default=None,
                                                   description="UTC timestamp when pipeline finished")
    completed_stages:   List[Stage]     = Field(
                            default_factory=list,
                            description="Stages that have successfully completed",
                        )
    skipped_stages:     List[Stage]     = Field(
                            default_factory=list,
                            description="Stages explicitly disabled in config",
                        )
    stage_stats:        Dict[str, StageStats] = Field(
                            default_factory=dict,
                            description="Per-stage statistics keyed by Stage value string",
                        )

    # Out-of-scope audit log -------------------------------------------------
    scoped_out_targets: List[Dict[str, Any]] = Field(
                            default_factory=list,
                            description="Targets dropped by ScopeValidator — {target, stage, reason}",
                        )

    model_config = {"frozen": False}

    # ------------------------------------------------------------------
    # Subdomain helpers
    # ------------------------------------------------------------------

    def get_subdomain(self, fqdn: str) -> Optional[Subdomain]:
        """Look up an existing Subdomain by FQDN (case-insensitive)."""
        fqdn = fqdn.strip().lower()
        for sd in self.subdomains:
            if sd.subdomain == fqdn:
                return sd
        return None

    def upsert_subdomain(self, subdomain: Subdomain) -> Subdomain:
        """
        Insert a new subdomain or return the existing one with the same FQDN.

        If the FQDN already exists, the existing object is returned so that
        callers can enrich it rather than creating a duplicate.
        """
        existing = self.get_subdomain(subdomain.subdomain)
        if existing is not None:
            return existing
        self.subdomains.append(subdomain)
        return subdomain

    def live_subdomains(self) -> List[Subdomain]:
        """Return only subdomains confirmed live by the HTTP_PROBE stage."""
        return [sd for sd in self.subdomains if sd.is_live]

    def in_scope_subdomains(self) -> List[Subdomain]:
        """Return subdomains that passed scope validation."""
        return [sd for sd in self.subdomains if sd.in_scope]

    # ------------------------------------------------------------------
    # Stage result helpers
    # ------------------------------------------------------------------

    def add_stage_results(self, stage: Stage, results: List[ReconResult]) -> None:
        """Append a batch of results for a stage, creating the list if needed."""
        key = stage.value
        if key not in self.stage_results:
            self.stage_results[key] = []
        self.stage_results[key].extend(results)

    def get_stage_results(self, stage: Stage) -> List[ReconResult]:
        """Return all results collected for a given stage (empty list if none)."""
        return self.stage_results.get(stage.value, [])

    def mark_stage_complete(self, stage: Stage) -> None:
        """Record a stage as successfully completed."""
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)

    def is_stage_complete(self, stage: Stage) -> bool:
        """Return True if the stage has already been completed (for --resume)."""
        return stage in self.completed_stages

    # ------------------------------------------------------------------
    # Scope audit log
    # ------------------------------------------------------------------

    def log_scoped_out(self, target: str, stage: Stage, reason: str = "") -> None:
        """Record a target that was silently dropped by ScopeValidator."""
        self.scoped_out_targets.append({
            "target": target,
            "stage":  stage.value,
            "reason": reason,
        })

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return a human-readable summary dict suitable for summary.md generation."""
        return {
            "run_id":             self.run_id,
            "target":             self.target,
            "scope":              self.scope,
            "started_at":         self.started_at.isoformat(),
            "completed_at":       self.completed_at.isoformat() if self.completed_at else None,
            "completed_stages":   [s.value for s in self.completed_stages],
            "skipped_stages":     [s.value for s in self.skipped_stages],
            "total_subdomains":   len(self.subdomains),
            "live_subdomains":    len(self.live_subdomains()),
            "scoped_out_targets": len(self.scoped_out_targets),
            "total_urls":         sum(len(sd.urls) for sd in self.subdomains),
            "total_ports":        sum(len(sd.ports) for sd in self.subdomains),
            "stage_stats":        {
                k: {
                    "duration_seconds": v.duration_seconds,
                    "tools_run":        v.tools_run,
                    "tools_failed":     v.tools_failed,
                    "tools_skipped":    v.tools_skipped,
                    "items_in":         v.items_in,
                    "items_out":        v.items_out,
                    "items_scoped_out": v.items_scoped_out,
                }
                for k, v in self.stage_stats.items()
            },
        }
