"""
pipeline/runner.py
~~~~~~~~~~~~~~~~~~
PipelineRunner — top-level orchestrator.

CONTRACT
--------
PipelineConfig
    Dataclass holding the full pipeline configuration (stages enabled,
    concurrency, tool overrides, output directory).

PipelineRunner(config, state_manager)
    Owns one StageRunner per stage.  Shared across the lifetime of a
    single pipeline execution.

async run(target, scope, resume=False, stage_filter=None) -> PipelineState
    Entry point for one complete pipeline execution.

    Execution order (strict):
    1. Call discover_tools() to auto-import all plugin modules.
    2. Create or load PipelineState:
       - resume=True  → load checkpoint via StateManager.load(); if not
         found, start fresh with a WARNING.
       - resume=False → always start fresh (StateManager.new_state()).
    3. Build ScopeValidator from state.scope.
    4. For each Stage in canonical order (Stage.ordered()):
       a. Skip the OUTPUT pseudo-stage (handled by output writers).
       b. If the stage is in state.completed_stages → skip (resume logic).
       c. If the stage is disabled in config.stages → skip.
       d. If stage_filter supplied and stage not in it → skip.
       e. Derive targets for this stage from state (see _targets_for_stage).
       f. Run ScopeValidator.filter(targets) as the STAGE-TRANSITION CHECK
          — this is in addition to the check inside StageRunner.
       g. Execute StageRunner.run(targets, state).
       h. Checkpoint: StateManager.save(state) after each stage.
    5. Set state.completed_at = datetime.now(UTC).
    6. Return the fully-populated PipelineState.

Stage input/output chain
    Each stage's input is derived from the accumulated PipelineState,
    not from the previous stage's raw ReconResult list:

    SUBDOMAIN_ENUM  → [target]                      (root domain)
    DNS_RESOLUTION  → [sd.subdomain for sd in state.subdomains]
    HTTP_PROBE      → [sd.subdomain for sd in in_scope_subdomains]
    PORT_SCAN       → [sd.subdomain for sd in live_subdomains]
    URL_DISCOVERY   → [sd.subdomain for sd in live_subdomains]
    FINGERPRINT     → [sd.subdomain for sd in live_subdomains]
    OUTPUT          → skipped (handled by output writers)

Scope enforcement
    ScopeValidator.filter() is called AT EVERY STAGE TRANSITION by the
    PipelineRunner before passing targets to StageRunner.  StageRunner
    also performs its own internal check.  Two layers of protection.

Error resilience
    - A StageRunner that raises (should never happen given our contract)
      is caught here; the error is logged and the pipeline skips to the
      next stage.
    - A failed checkpoint write is logged but does NOT abort the pipeline.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from recon_node.models import PipelineState, Stage
from recon_node.pipeline.scope import ScopeValidator
from recon_node.pipeline.stage import StageConfig, StageRunner
from recon_node.pipeline.state import StateManager
from recon_node.tools.base import discover_tools

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class PipelineConfig:
    """
    Full pipeline configuration.

    Mirrors the structure of config.yaml so that the YAML loader
    can populate this directly.

    Attributes
    ----------
    output_dir:
        Root directory for all output artifacts.
    stages:
        Dict mapping Stage.value strings to bool.  True = run, False = skip.
        Defaults to all stages enabled.
    concurrent_tools:
        Global semaphore size — max tools running in parallel per stage.
    tool_overrides:
        Dict of tool class name → bool.  Propagated to every StageConfig.
    tools_package:
        Dotted package name passed to discover_tools().  Override for tests.
    """
    output_dir:       str            = "./output"
    stages:           Dict[str, bool] = dataclasses.field(
                          default_factory=lambda: {s.value: True for s in Stage.ordered()}
                      )
    concurrent_tools: int            = 3
    tool_overrides:   Dict[str, bool] = dataclasses.field(default_factory=dict)
    tools_package:    str            = "recon_node.tools"


# ---------------------------------------------------------------------------
# PipelineRunner
# ---------------------------------------------------------------------------

class PipelineRunner:
    """
    Orchestrates all pipeline stages for a single recon run.

    Parameters
    ----------
    config:
        PipelineConfig controlling which stages/tools run and how.
    state_manager:
        StateManager for checkpoint persistence.  Create with:
        ``StateManager(output_dir=config.output_dir)``
    """

    def __init__(
        self,
        config:        PipelineConfig,
        state_manager: StateManager,
    ) -> None:
        self.config        = config
        self.state_manager = state_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        target:       str,
        scope:        List[str],
        resume:       bool                    = False,
        stage_filter: Optional[Set[Stage]]    = None,
    ) -> PipelineState:
        """
        Execute the full recon pipeline against ``target``.

        Parameters
        ----------
        target:
            Root domain to scan (e.g. ``"example.com"``).
        scope:
            In-scope patterns (e.g. ``["*.example.com", "api.example.com"]``).
        resume:
            If True, load the last checkpoint and skip completed stages.
            If no checkpoint is found, a WARNING is logged and the run
            starts fresh.
        stage_filter:
            Optional whitelist of Stage values to execute.  Stages absent
            from this set are skipped even if enabled in config.
            Pass ``None`` to run all enabled stages.

        Returns
        -------
        PipelineState
            The fully populated state after all stages complete.
        """
        log.info(
            "PipelineRunner.run: target=%s scope=%s resume=%s stages=%s",
            target, scope, resume,
            [s.value for s in stage_filter] if stage_filter else "all",
        )

        # --- 1. Auto-discover tool plugins ----------------------------------
        n_modules = discover_tools(self.config.tools_package)
        log.info("discover_tools: %d modules imported", n_modules)

        # --- 2. Create or restore PipelineState ----------------------------
        state = self._init_state(target, scope, resume)
        # Build scope validator. Include the root target itself as an exact-match
        # pattern — "example.com" won't match "*.example.com" (wildcard covers
        # subdomains only), but we always want to pass it to SUBDOMAIN_ENUM tools.
        effective_scope = list(state.scope)
        if target not in effective_scope:
            effective_scope.append(target)
        validator = ScopeValidator(effective_scope)

        log.info(
            "Pipeline started: run_id=%s target=%s", state.run_id, state.target
        )

        # --- 3. Execute stages in canonical order --------------------------
        for stage in Stage.ordered():

            # Skip the OUTPUT pseudo-stage — it is handled by output writers
            if stage == Stage.OUTPUT:
                log.debug("Stage OUTPUT: delegated to output writers — skipping")
                continue

            # Resume: already completed → skip
            if state.is_stage_complete(stage):
                log.info("Stage %s: already completed (resume) — skipping", stage.value)
                continue

            # Config: stage disabled
            if not self.config.stages.get(stage.value, True):
                log.info("Stage %s: disabled in config — skipping", stage.value)
                state.skipped_stages.append(stage)
                continue

            # CLI stage filter
            if stage_filter is not None and stage not in stage_filter:
                log.info("Stage %s: not in stage_filter — skipping", stage.value)
                state.skipped_stages.append(stage)
                continue

            # --- 3e. Derive targets -----------------------------------------
            raw_targets = self._targets_for_stage(stage, state, target)

            # --- 3f. Stage-transition scope check (extra safety layer) ------
            # NOTE: SUBDOMAIN_ENUM is exempt — the root target (e.g. "example.com")
            # intentionally does NOT match "*.example.com" (wildcards cover subdomains
            # only).  The root target is always valid input for enumeration.
            if stage == Stage.SUBDOMAIN_ENUM:
                in_scope_targets = raw_targets
                scoped_out       = []
            else:
                in_scope_targets, scoped_out = validator.filter(raw_targets)
                for t in scoped_out:
                    state.log_scoped_out(
                        t, stage,
                        reason="pre-stage scope filter in PipelineRunner",
                    )

            log.info(
                "Stage %s: %d targets (%d scoped-out at runner level)",
                stage.value, len(in_scope_targets), len(scoped_out),
            )

            # --- 3g. Build and run StageRunner ------------------------------
            stage_cfg = StageConfig(
                concurrent_tools = self.config.concurrent_tools,
                enabled          = True,   # already checked above
                tool_overrides   = dict(self.config.tool_overrides),
            )
            runner = StageRunner(stage, validator, stage_cfg)

            try:
                await runner.run(in_scope_targets, state)
            except Exception as exc:
                # Should never happen — StageRunner catches everything
                log.error(
                    "PipelineRunner: StageRunner for %s raised unexpectedly: %s",
                    stage.value, exc, exc_info=True,
                )

            # --- 3h. Checkpoint --------------------------------------------
            try:
                self.state_manager.save(state)
            except OSError as exc:
                log.error(
                    "PipelineRunner: checkpoint save failed after stage %s: %s",
                    stage.value, exc,
                )
                # Non-fatal — pipeline continues without checkpoint

        # --- 4. Finalize ---------------------------------------------------
        state.completed_at = datetime.now(timezone.utc)
        log.info(
            "Pipeline complete: target=%s run_id=%s stages=%s",
            state.target, state.run_id,
            [s.value for s in state.completed_stages],
        )
        return state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_state(
        self,
        target: str,
        scope:  List[str],
        resume: bool,
    ) -> PipelineState:
        """
        Return a PipelineState — resumed from disk or freshly created.
        """
        if resume:
            existing = self.state_manager.load(target)
            if existing is not None:
                log.info(
                    "Resume: loaded checkpoint for %s (run_id=%s, "
                    "completed_stages=%s)",
                    target, existing.run_id,
                    [s.value for s in existing.completed_stages],
                )
                return existing
            log.warning(
                "Resume requested for %s but no checkpoint found — starting fresh",
                target,
            )

        return self.state_manager.new_state(target, scope)

    @staticmethod
    def _targets_for_stage(
        stage:  Stage,
        state:  PipelineState,
        target: str,
    ) -> List[str]:
        """
        Derive the appropriate target list for a stage from the current state.

        Stage input chain:
            SUBDOMAIN_ENUM  → [root domain]
            DNS_RESOLUTION  → all discovered subdomain FQDNs
            HTTP_PROBE      → in-scope subdomain FQDNs (may or may not have IPs yet)
            PORT_SCAN       → live subdomain FQDNs/IPs
            URL_DISCOVERY   → live subdomain FQDNs
            FINGERPRINT     → live subdomain FQDNs
        """
        if stage == Stage.SUBDOMAIN_ENUM:
            return [target]

        if stage == Stage.DNS_RESOLUTION:
            return [sd.subdomain for sd in state.in_scope_subdomains()]

        if stage == Stage.HTTP_PROBE:
            return [sd.subdomain for sd in state.in_scope_subdomains()]

        if stage in (Stage.PORT_SCAN, Stage.URL_DISCOVERY, Stage.FINGERPRINT):
            return [sd.subdomain for sd in state.live_subdomains()
                    if sd.in_scope]

        return []

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @classmethod
    def from_config_dict(cls, cfg: dict) -> "PipelineRunner":
        """
        Build a PipelineRunner from a raw config dict (as loaded from YAML).

        Expected keys (all optional, fall back to defaults):
            output_dir, stages, rate_limit.concurrent_tools, tools.*
        """
        output_dir       = cfg.get("output_dir", "./output")
        concurrent_tools = cfg.get("rate_limit", {}).get("concurrent_tools", 3)
        stages_cfg       = cfg.get("stages", {})
        # Normalise: ensure every stage has an entry
        stages = {s.value: stages_cfg.get(s.value, True) for s in Stage.ordered()}

        config = PipelineConfig(
            output_dir       = output_dir,
            stages           = stages,
            concurrent_tools = concurrent_tools,
        )
        state_mgr = StateManager(output_dir=output_dir)
        return cls(config=config, state_manager=state_mgr)
