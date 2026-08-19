"""
pipeline/stage.py
~~~~~~~~~~~~~~~~~
StageRunner — the async parallel execution engine for a single pipeline stage.

CONTRACT
--------
StageRunner(stage, validator, config)
    ``stage``     — the Stage enum value this runner owns.
    ``validator`` — a ScopeValidator instance shared across all stages.
    ``config``    — a StageConfig dataclass with concurrency + enabled flags.

async run(targets, state) -> List[ReconResult]
    1. Filter ``targets`` through ScopeValidator.
       - Out-of-scope targets are logged to ``state.log_scoped_out()`` and
         silently dropped.  They are NEVER passed to a tool.
    2. Look up all tool classes registered for this stage in REGISTRY.
    3. Instantiate each tool class.  Skip any where is_installed() == False
       (log a WARNING; pipeline continues).
    4. Run all installed tools in parallel using asyncio.gather() bounded by
       a semaphore of size ``config.concurrent_tools``.
    5. Each tool's run() coroutine receives the full (filtered) target list
       and the live PipelineState.
    6. Collect all ReconResult objects from all tools.
    7. Call ``state.add_stage_results(stage, results)`` with the full batch.
    8. Update ``state.stage_stats[stage]`` with timing, counts, tool names.
    9. Call ``state.mark_stage_complete(stage)``.
    10. Return the full result list.

Error handling
    - A tool whose run() propagates an exception (contract violation) is
      caught here as a last-resort safety net.  A ReconResult.failure() is
      synthesized and the pipeline continues.
    - If NO tools are installed for a stage, log a WARNING and return [].
    - If NO targets survive scope filtering, log INFO and return [].

Parallelism
    - Tools within a stage run concurrently (asyncio.gather).
    - The ``concurrent_tools`` semaphore caps how many tools execute at once.
    - Tools within a single tool call (targets × tool) are handled internally
      by the tool itself.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import datetime, timezone
from typing import List, Optional

from recon_node.models import PipelineState, ReconResult, Stage, StageStats
from recon_node.pipeline.scope import ScopeValidator
from recon_node.tools.base import REGISTRY, ReconTool

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class StageConfig:
    """
    Runtime configuration for a single StageRunner.

    Attributes
    ----------
    concurrent_tools : int
        Maximum number of tools that may run in parallel within this stage.
        Default: 3 (matches config.yaml spec).
    enabled : bool
        If False, run() returns immediately with an empty list and logs INFO.
    tool_overrides : dict
        Per-tool key→bool flags.  Key = tool class name; value = enabled.
        Tools absent from this dict default to enabled.
    """
    concurrent_tools: int   = 3
    enabled:          bool  = True
    tool_overrides:   dict  = dataclasses.field(default_factory=dict)


# ---------------------------------------------------------------------------
# StageRunner
# ---------------------------------------------------------------------------

class StageRunner:
    """
    Runs all registered tools for one pipeline stage in parallel.

    Instantiate one StageRunner per stage in PipelineRunner.
    The instance is NOT reusable across multiple pipeline runs —
    create a fresh one for each run.

    Parameters
    ----------
    stage:
        The pipeline stage this runner is responsible for.
    validator:
        A ScopeValidator configured with the current run's scope list.
        Shared across all StageRunners — it is stateless and thread-safe.
    config:
        StageConfig controlling concurrency and enabled/disabled flags.
    """

    def __init__(
        self,
        stage:     Stage,
        validator: ScopeValidator,
        config:    Optional[StageConfig] = None,
    ) -> None:
        self.stage     = stage
        self.validator = validator
        self.config    = config or StageConfig()
        self._lock     = asyncio.Lock()   # guards state mutations from parallel tools

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        targets: List[str],
        state:   PipelineState,
    ) -> List[ReconResult]:
        """
        Execute all installed tools for this stage against ``targets``.

        Parameters
        ----------
        targets:
            Input target list appropriate for this stage (e.g. root domains
            for SUBDOMAIN_ENUM, FQDNs for DNS_RESOLUTION, etc.).
        state:
            The live PipelineState.  Mutated in-place under ``self._lock``.

        Returns
        -------
        List[ReconResult]
            All results from all tools (success + failure mixed).
        """
        started_at = datetime.now(timezone.utc)

        # --- 0. Stage disabled check ----------------------------------------
        if not self.config.enabled:
            log.info("Stage %s is disabled in config — skipping", self.stage.value)
            async with self._lock:
                state.skipped_stages.append(self.stage)
            return []

        # --- 1. Scope filtering ---------------------------------------------
        in_scope, out_of_scope = self.validator.filter(targets)

        async with self._lock:
            for target in out_of_scope:
                state.log_scoped_out(
                    target, self.stage,
                    reason="failed scope validation at stage transition",
                )

        log.info(
            "Stage %s: %d targets in-scope, %d dropped",
            self.stage.value, len(in_scope), len(out_of_scope),
        )

        if not in_scope:
            log.info("Stage %s: no in-scope targets — skipping", self.stage.value)
            self._record_stats(state, started_at,
                               items_in=len(targets),
                               items_out=0,
                               items_scoped_out=len(out_of_scope),
                               tools_run=[], tools_failed=[])
            return []

        # --- 2. Resolve tools -----------------------------------------------
        tool_classes = REGISTRY.tools_for_stage(self.stage)
        if not tool_classes:
            log.warning(
                "Stage %s: no tools registered — did you call discover_tools()?",
                self.stage.value,
            )
            return []

        # Filter by tool-level config overrides
        tool_classes = [
            cls for cls in tool_classes
            if self.config.tool_overrides.get(cls.__name__, True)
        ]

        # --- 3. Instantiate and check is_installed() ------------------------
        tools_to_run: List[ReconTool] = []
        skipped_names: List[str]      = []

        for cls in tool_classes:
            tool = cls()
            if not tool.is_installed():
                log.warning(
                    "Stage %s: tool %s not installed — skipping",
                    self.stage.value, tool.tool_name,
                )
                skipped_names.append(tool.tool_name)
                continue
            tools_to_run.append(tool)

        if not tools_to_run:
            log.warning(
                "Stage %s: no installed tools — cannot execute",
                self.stage.value,
            )
            self._record_stats(state, started_at,
                               items_in=len(targets),
                               items_out=0,
                               items_scoped_out=len(out_of_scope),
                               tools_run=[], tools_failed=[],
                               tools_skipped=skipped_names)
            return []

        log.info(
            "Stage %s: running %d tool(s) in parallel (concurrent_tools=%d): %s",
            self.stage.value,
            len(tools_to_run),
            self.config.concurrent_tools,
            [t.tool_name for t in tools_to_run],
        )

        # --- 4. Parallel execution with semaphore ---------------------------
        semaphore = asyncio.Semaphore(self.config.concurrent_tools)

        async def _run_one(tool: ReconTool) -> tuple[str, List[ReconResult]]:
            async with semaphore:
                try:
                    results = await tool.run(in_scope, state)
                    if results is None:
                        # Contract violation — synthesize failure result
                        log.error(
                            "Stage %s: tool %s returned None (contract violation)",
                            self.stage.value, tool.tool_name,
                        )
                        results = [ReconResult.failure(
                            tool=tool.tool_name,
                            stage=self.stage,
                            target="(all targets)",
                            error="tool.run() returned None — contract violation",
                        )]
                except Exception as exc:
                    # Last-resort catch — tool broke its own contract
                    log.error(
                        "Stage %s: tool %s raised unexpectedly: %s",
                        self.stage.value, tool.tool_name, exc,
                        exc_info=True,
                    )
                    results = [ReconResult.failure(
                        tool=tool.tool_name,
                        stage=self.stage,
                        target="(all targets)",
                        error=f"uncaught exception: {exc}",
                    )]
                return tool.tool_name, results

        gathered = await asyncio.gather(*(_run_one(t) for t in tools_to_run))

        # --- 5. Collect results ---------------------------------------------
        all_results:  List[ReconResult] = []
        tools_run:    List[str]         = []
        tools_failed: List[str]         = []

        for tool_name, results in gathered:
            tools_run.append(tool_name)
            all_results.extend(results)
            if any(not r.success for r in results):
                tools_failed.append(tool_name)

        # --- 6–9. Update state ----------------------------------------------
        async with self._lock:
            state.add_stage_results(self.stage, all_results)
            state.mark_stage_complete(self.stage)

        self._record_stats(
            state,
            started_at,
            items_in=len(targets),
            items_out=len(all_results),
            items_scoped_out=len(out_of_scope),
            tools_run=tools_run,
            tools_failed=tools_failed,
            tools_skipped=skipped_names,
        )

        log.info(
            "Stage %s complete: %d results from %d tool(s)",
            self.stage.value, len(all_results), len(tools_run),
        )
        return all_results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_stats(
        self,
        state:             PipelineState,
        started_at:        datetime,
        items_in:          int,
        items_out:         int,
        items_scoped_out:  int,
        tools_run:         List[str],
        tools_failed:      List[str],
        tools_skipped:     Optional[List[str]] = None,
    ) -> None:
        """Write StageStats into state.stage_stats under the stage key."""
        stats = StageStats(
            stage            = self.stage,
            started_at       = started_at,
            completed_at     = datetime.now(timezone.utc),
            tools_run        = tools_run,
            tools_failed     = tools_failed,
            tools_skipped    = tools_skipped or [],
            items_in         = items_in,
            items_out        = items_out,
            items_scoped_out = items_scoped_out,
        )
        state.stage_stats[self.stage.value] = stats

    @property
    def is_enabled(self) -> bool:
        """Return True if this stage is enabled in config."""
        return self.config.enabled
