"""
tests/test_stage_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test suite for StageRunner (pipeline/stage.py).

All tools used here are in-process stubs — no real binaries required.
Each test registers its own private tools into a fresh, isolated registry
to prevent cross-test contamination.

Run:
    $env:PYTHONPATH = "<repo-root>"
    .venv/Scripts/python tests/test_stage_contract.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from typing import List

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    from recon_node.pipeline.stage import StageRunner  # noqa: F401

_bootstrap()

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.pipeline.scope import ScopeValidator
from recon_node.pipeline.stage import StageConfig, StageRunner
from recon_node.tools.base import ReconTool, _ToolRegistry


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _state(scope: List[str] | None = None) -> PipelineState:
    """Fresh PipelineState for each test."""
    return PipelineState(
        run_id=str(uuid.uuid4()),
        target="example.com",
        scope=scope or ["*.example.com"],
    )


def _validator(scope: List[str] | None = None) -> ScopeValidator:
    return ScopeValidator(scope or ["*.example.com"])


def _runner(
    stage:  Stage = Stage.SUBDOMAIN_ENUM,
    scope:  List[str] | None = None,
    config: StageConfig | None = None,
    registry: _ToolRegistry | None = None,
) -> StageRunner:
    """Build a StageRunner with an isolated registry (default = REGISTRY)."""
    runner = StageRunner(
        stage     = stage,
        validator = _validator(scope),
        config    = config or StageConfig(),
    )
    if registry is not None:
        # Monkey-patch registry for this runner's scope
        runner._registry = registry
    return runner


def run_async(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tool stubs — registered into isolated private registries
# ---------------------------------------------------------------------------

def _make_registry_with_tools(*tool_classes) -> _ToolRegistry:
    """
    Create a private _ToolRegistry and register the given classes into it,
    using the _stage attribute already stamped by @register_tool.
    """
    reg = _ToolRegistry()
    for cls in tool_classes:
        reg._register(cls._stage, cls)
    return reg


class _OkTool(ReconTool):
    """Always succeeds, returns one result per target."""
    name   = "OkTool"
    binary = ""
    _stage = Stage.SUBDOMAIN_ENUM

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        return [self._make_result(t, data={"found": [f"sub.{t}"]}) for t in targets]

    def is_installed(self) -> bool:
        return True


class _FailingTool(ReconTool):
    """Returns a failure result for every target."""
    name   = "FailingTool"
    binary = ""
    _stage = Stage.SUBDOMAIN_ENUM

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        return [ReconResult.failure(self.tool_name, self.stage, t, "simulated error")
                for t in targets]

    def is_installed(self) -> bool:
        return True


class _MissingTool(ReconTool):
    """is_installed() returns False — should be skipped."""
    name   = "MissingTool"
    binary = "__never_exists_xyzzy__"
    _stage = Stage.SUBDOMAIN_ENUM

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        raise RuntimeError("This tool should never be called")

    def is_installed(self) -> bool:
        return False


class _SlowTool(ReconTool):
    """Sleeps briefly so parallelism is measurable."""
    name   = "SlowTool"
    binary = ""
    _stage = Stage.DNS_RESOLUTION

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        await asyncio.sleep(0.05)
        return [self._make_result(t, data={}) for t in targets]

    def is_installed(self) -> bool:
        return True


class _SlowTool2(ReconTool):
    name   = "SlowTool2"
    binary = ""
    _stage = Stage.DNS_RESOLUTION

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        await asyncio.sleep(0.05)
        return [self._make_result(t, data={}) for t in targets]

    def is_installed(self) -> bool:
        return True


class _SlowTool3(ReconTool):
    name   = "SlowTool3"
    binary = ""
    _stage = Stage.DNS_RESOLUTION

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        await asyncio.sleep(0.05)
        return [self._make_result(t, data={}) for t in targets]

    def is_installed(self) -> bool:
        return True


class _ExplodingTool(ReconTool):
    """Violates contract by raising — StageRunner must catch."""
    name   = "ExplodingTool"
    binary = ""
    _stage = Stage.HTTP_PROBE

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        raise RuntimeError("I broke the contract")

    def is_installed(self) -> bool:
        return True


class _NoneReturningTool(ReconTool):
    """Violates contract by returning None — StageRunner must handle."""
    name   = "NoneReturningTool"
    binary = ""
    _stage = Stage.PORT_SCAN

    async def run(self, targets, state):
        return None  # type: ignore — intentional contract violation

    def is_installed(self) -> bool:
        return True


class _DisabledByOverrideTool(ReconTool):
    name   = "DisabledByOverrideTool"
    binary = ""
    _stage = Stage.URL_DISCOVERY

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        raise RuntimeError("Should never be called")

    def is_installed(self) -> bool:
        return True


# ===========================================================================
# CLAUSE 1 — Scope filtering: out-of-scope targets dropped BEFORE tools run
# ===========================================================================

def test_scope_filtering_drops_targets() -> None:
    """StageRunner must drop out-of-scope targets before calling any tool."""
    called_with: List[List[str]] = []

    class _SpyTool(ReconTool):
        name   = "SpyTool"
        binary = ""
        _stage = Stage.SUBDOMAIN_ENUM

        async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
            called_with.append(list(targets))
            return [self._make_result(t, {}) for t in targets]

        def is_installed(self) -> bool:
            return True

    reg = _make_registry_with_tools(_SpyTool)
    runner = StageRunner(Stage.SUBDOMAIN_ENUM, _validator(["*.example.com"]),
                         StageConfig())
    runner._registry = reg  # type: ignore

    # Patch REGISTRY lookup in the runner
    import recon_node.pipeline.stage as _stage_mod
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        targets = ["api.example.com", "evil.com", "sub.example.com", "attacker.io"]
        run_async(runner.run(targets, state))

        assert len(called_with) == 1, f"Tool called {len(called_with)} times"
        tool_targets = called_with[0]
        assert "api.example.com" in tool_targets
        assert "sub.example.com" in tool_targets
        assert "evil.com"        not in tool_targets
        assert "attacker.io"     not in tool_targets
    finally:
        _stage_mod.REGISTRY = orig

    print("  [PASS] clause 1 -- out-of-scope targets dropped before tool.run()")


# ===========================================================================
# CLAUSE 2 — Out-of-scope targets logged to state.scoped_out_targets
# ===========================================================================

def test_scoped_out_logged_to_state() -> None:
    """Out-of-scope targets must appear in state.scoped_out_targets."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_OkTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state(["*.example.com"])
        targets = ["api.example.com", "evil.com", "bad.io"]
        run_async(StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
                  .run(targets, state))

        scoped_out_targets = [e["target"] for e in state.scoped_out_targets]
        assert "evil.com" in scoped_out_targets
        assert "bad.io"   in scoped_out_targets
        assert "api.example.com" not in scoped_out_targets
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 2 -- out-of-scope targets logged in state.scoped_out_targets")


# ===========================================================================
# CLAUSE 3 — Tools NOT installed are silently skipped, pipeline continues
# ===========================================================================

def test_missing_tool_skipped_pipeline_continues() -> None:
    """A tool where is_installed()==False must be skipped; OkTool still runs."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_OkTool, _MissingTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
            .run(["api.example.com"], state)
        )
        # Results must come from OkTool only
        assert len(results) == 1
        assert results[0].tool == "OkTool"
        assert results[0].success is True

        # MissingTool must be in tools_skipped, NOT tools_failed
        stats = state.stage_stats.get(Stage.SUBDOMAIN_ENUM.value)
        assert stats is not None, "No stats written"
        assert "MissingTool" in stats.tools_skipped, \
            f"MissingTool not in tools_skipped: {stats.tools_skipped}"
        assert "MissingTool" not in stats.tools_failed, \
            f"MissingTool wrongly in tools_failed: {stats.tools_failed}"
        assert "MissingTool" not in stats.tools_run, \
            f"MissingTool wrongly in tools_run: {stats.tools_run}"
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 3 -- missing tool skipped, other tools still ran")


# ===========================================================================
# CLAUSE 4 — Tools run in parallel (asyncio.gather)
# ===========================================================================

def test_tools_run_in_parallel() -> None:
    """Three tools each sleeping 50ms should finish in ~50ms, not ~150ms."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_SlowTool, _SlowTool2, _SlowTool3)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        t0      = time.perf_counter()
        run_async(
            StageRunner(Stage.DNS_RESOLUTION, _validator(), StageConfig(concurrent_tools=3))
            .run(["api.example.com"], state)
        )
        elapsed = time.perf_counter() - t0
        # Parallel: should finish in ~50ms (+overhead), not 150ms
        assert elapsed < 0.25, f"Tools ran sequentially? elapsed={elapsed:.3f}s"
    finally:
        _stage_mod.REGISTRY = orig
    print(f"  [PASS] clause 4 -- 3 x 50ms tools ran in parallel (~{elapsed*1000:.0f}ms)")


# ===========================================================================
# CLAUSE 5 — concurrent_tools semaphore limits parallelism
# ===========================================================================

def test_semaphore_limits_concurrency() -> None:
    """concurrent_tools=1 must serialize tool execution."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_SlowTool, _SlowTool2)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        t0      = time.perf_counter()
        run_async(
            StageRunner(Stage.DNS_RESOLUTION, _validator(), StageConfig(concurrent_tools=1))
            .run(["api.example.com"], state)
        )
        elapsed = time.perf_counter() - t0
        # Serial: must be >= 2 × 50ms
        assert elapsed >= 0.08, f"Semaphore not serializing? elapsed={elapsed:.3f}s"
    finally:
        _stage_mod.REGISTRY = orig
    print(f"  [PASS] clause 5 -- concurrent_tools=1 serialized execution ({elapsed*1000:.0f}ms)")


# ===========================================================================
# CLAUSE 6 — state.add_stage_results() called with all tool results
# ===========================================================================

def test_results_written_to_state() -> None:
    """All results must be committed to state.stage_results."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_OkTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        targets = ["api.example.com", "mail.example.com"]
        run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
            .run(targets, state)
        )
        stored = state.get_stage_results(Stage.SUBDOMAIN_ENUM)
        assert len(stored) == 2   # one per target from _OkTool
        assert all(isinstance(r, ReconResult) for r in stored)
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 6 -- state.add_stage_results() called with all results")


# ===========================================================================
# CLAUSE 7 — state.mark_stage_complete() called after successful run
# ===========================================================================

def test_stage_marked_complete() -> None:
    """StageRunner must call state.mark_stage_complete() on success."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_OkTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state = _state()
        assert not state.is_stage_complete(Stage.SUBDOMAIN_ENUM)
        run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
            .run(["api.example.com"], state)
        )
        assert state.is_stage_complete(Stage.SUBDOMAIN_ENUM), \
            "Stage not marked complete after run()"
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 7 -- stage marked complete in state after run()")


# ===========================================================================
# CLAUSE 8 — StageStats written with correct timing and counts
# ===========================================================================

def test_stage_stats_written() -> None:
    """StageStats must be written to state with correct counts."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_OkTool, _FailingTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        targets = ["api.example.com", "evil.com"]   # 1 in-scope, 1 out
        run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
            .run(targets, state)
        )
        stats = state.stage_stats.get(Stage.SUBDOMAIN_ENUM.value)
        assert stats is not None,              "No stats written"
        assert stats.items_in         == 2,    f"items_in={stats.items_in}"
        assert stats.items_scoped_out == 1,    f"scoped_out={stats.items_scoped_out}"
        assert stats.items_out        >= 1,    f"items_out={stats.items_out}"
        assert "OkTool"     in stats.tools_run
        assert "FailingTool" in stats.tools_run
        assert stats.duration_seconds is not None
        assert stats.duration_seconds >= 0
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 8 -- StageStats written with correct counts and timing")


# ===========================================================================
# CLAUSE 9 — Contract violation: tool raises — synthesized failure result
# ===========================================================================

def test_exploding_tool_contained() -> None:
    """A tool that raises must be caught; ReconResult.failure synthesized."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_ExplodingTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.HTTP_PROBE, _validator(), StageConfig())
            .run(["api.example.com"], state)
        )
        assert len(results) == 1
        r = results[0]
        assert r.success is False
        assert "uncaught exception" in r.error
        assert r.tool == "ExplodingTool"
        # Stage still marked complete (we collected results, however partial)
        assert state.is_stage_complete(Stage.HTTP_PROBE)
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 9 -- raising tool caught, ReconResult.failure synthesized")


# ===========================================================================
# CLAUSE 10 — Contract violation: tool returns None — handled gracefully
# ===========================================================================

def test_none_returning_tool_handled() -> None:
    """A tool that returns None must be handled without crashing."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_NoneReturningTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.PORT_SCAN, _validator(), StageConfig())
            .run(["api.example.com"], state)
        )
        assert len(results) == 1
        assert results[0].success is False
        assert "None" in results[0].error
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 10 -- None-returning tool handled without crash")


# ===========================================================================
# CLAUSE 11 — Stage disabled in config: returns [] immediately
# ===========================================================================

def test_disabled_stage_returns_empty() -> None:
    """When config.enabled=False, run() must return [] and not call any tool."""
    import recon_node.pipeline.stage as _stage_mod
    called = []

    class _NeverCallTool(ReconTool):
        name = "NeverCallTool"; binary = ""; _stage = Stage.SUBDOMAIN_ENUM

        async def run(self, targets, state):
            called.append(True)
            return []

        def is_installed(self): return True

    reg = _make_registry_with_tools(_NeverCallTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(),
                        StageConfig(enabled=False))
            .run(["api.example.com"], state)
        )
        assert results == []
        assert called  == []
        assert Stage.SUBDOMAIN_ENUM in state.skipped_stages
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 11 -- disabled stage returns [], no tools called")


# ===========================================================================
# CLAUSE 12 — tool_overrides in config disable specific tools
# ===========================================================================

def test_tool_override_disables_tool() -> None:
    """config.tool_overrides={ToolName: False} must skip that tool."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_OkTool, _DisabledByOverrideTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.URL_DISCOVERY, _validator(),
                        StageConfig(tool_overrides={"_DisabledByOverrideTool": False}))
            .run(["api.example.com"], state)
        )
        # _DisabledByOverrideTool would raise if called — no exception = skipped
        assert all(r.tool != "_DisabledByOverrideTool" for r in results), \
            "Disabled tool still ran"
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 12 -- tool_overrides=False skips that specific tool")


# ===========================================================================
# CLAUSE 13 — No targets after scope filter: returns [] without calling tools
# ===========================================================================

def test_no_in_scope_targets_skips_tools() -> None:
    """If all targets are out-of-scope, run() returns [] without calling any tool."""
    import recon_node.pipeline.stage as _stage_mod
    called = []

    class _WatchTool(ReconTool):
        name = "WatchTool"; binary = ""; _stage = Stage.SUBDOMAIN_ENUM

        async def run(self, targets, state):
            called.append(targets)
            return []

        def is_installed(self): return True

    reg = _make_registry_with_tools(_WatchTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
            .run(["evil.com", "bad.io", "attacker.net"], state)
        )
        assert results == []
        assert called  == []   # tool never received any targets
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 13 -- all-out-of-scope: empty return, tools not called")


# ===========================================================================
# CLAUSE 14 — No registered tools: returns []
# ===========================================================================

def test_no_registered_tools_returns_empty() -> None:
    """If REGISTRY has no tools for this stage, run() returns [] cleanly."""
    import recon_node.pipeline.stage as _stage_mod
    reg  = _ToolRegistry()   # empty
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
            .run(["api.example.com"], state)
        )
        assert results == []
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 14 -- no registered tools: returns [] cleanly")


# ===========================================================================
# CLAUSE 15 — Failing tool results still accumulated; success tools not blocked
# ===========================================================================

def test_failing_tool_does_not_block_other_tools() -> None:
    """A tool returning failures must not prevent other tools from running."""
    import recon_node.pipeline.stage as _stage_mod
    reg = _make_registry_with_tools(_OkTool, _FailingTool)
    orig = _stage_mod.REGISTRY
    _stage_mod.REGISTRY = reg
    try:
        state   = _state()
        results = run_async(
            StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig())
            .run(["api.example.com"], state)
        )
        tools_seen = {r.tool for r in results}
        assert "OkTool"      in tools_seen, "OkTool never ran"
        assert "FailingTool" in tools_seen, "FailingTool results missing"
        ok_results   = [r for r in results if r.tool == "OkTool"]
        fail_results = [r for r in results if r.tool == "FailingTool"]
        assert all(r.success for r in ok_results)
        assert all(not r.success for r in fail_results)
    finally:
        _stage_mod.REGISTRY = orig
    print("  [PASS] clause 15 -- failing tool's failures don't block other tools")


# ===========================================================================
# CLAUSE 16 — StageRunner.is_enabled property reflects config
# ===========================================================================

def test_is_enabled_property() -> None:
    """StageRunner.is_enabled must reflect config.enabled."""
    r1 = StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig(enabled=True))
    r2 = StageRunner(Stage.SUBDOMAIN_ENUM, _validator(), StageConfig(enabled=False))
    assert r1.is_enabled is True
    assert r2.is_enabled is False
    print("  [PASS] clause 16 -- is_enabled property matches config")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_scope_filtering_drops_targets,
        test_scoped_out_logged_to_state,
        test_missing_tool_skipped_pipeline_continues,
        test_tools_run_in_parallel,
        test_semaphore_limits_concurrency,
        test_results_written_to_state,
        test_stage_marked_complete,
        test_stage_stats_written,
        test_exploding_tool_contained,
        test_none_returning_tool_handled,
        test_disabled_stage_returns_empty,
        test_tool_override_disables_tool,
        test_no_in_scope_targets_skips_tools,
        test_no_registered_tools_returns_empty,
        test_failing_tool_does_not_block_other_tools,
        test_is_enabled_property,
    ]

    passed = failed = 0
    print(f"\n{'='*62}")
    print("  StageRunner Contract Conformance Tests")
    print(f"{'='*62}")

    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  [FAIL] {fn.__name__}: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"{'='*62}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'='*62}\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
