"""
tests/test_plugin_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test suite for the ReconTool plugin contract.

Checks every clause documented in tools/base.py before Step 3 begins.

Run with:
    .venv/Scripts/python -m pytest tests/test_plugin_contract.py -v
or, without pytest:
    .venv/Scripts/python tests/test_plugin_contract.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import types
import uuid
from typing import List

# ---------------------------------------------------------------------------
# Minimal stubs so this file can run even before all pipeline/ modules exist
# ---------------------------------------------------------------------------


def _bootstrap() -> None:
    """Import the modules we need, fail fast if anything is missing."""
    import recon_node.models  # noqa: F401  — must succeed
    import recon_node.tools.base  # noqa: F401


_bootstrap()

from recon_node.models import PipelineState, ReconResult, Stage
from recon_node.tools.base import REGISTRY, ReconTool, discover_tools, register_tool


# ===========================================================================
# Helper: build a minimal PipelineState
# ===========================================================================

def _make_state() -> PipelineState:
    return PipelineState(
        run_id=str(uuid.uuid4()),
        target="example.com",
        scope=["*.example.com"],
    )


# ===========================================================================
# CONTRACT CLAUSE 1
# A tool MUST subclass ReconTool.
# ===========================================================================

def test_subclass_enforcement() -> None:
    """@register_tool must reject a non-ReconTool class."""
    try:
        @register_tool(stage=Stage.SUBDOMAIN_ENUM)
        class NotATool:
            pass
        assert False, "Should have raised TypeError"
    except TypeError as exc:
        assert "ReconTool subclasses" in str(exc), f"Wrong error: {exc}"
    print("  [PASS] clause 1 — non-ReconTool rejected by @register_tool")


# ===========================================================================
# CONTRACT CLAUSE 2
# @register_tool stamps _stage and registers in REGISTRY.
# ===========================================================================

@register_tool(stage=Stage.SUBDOMAIN_ENUM)
class _ContractDummyTool(ReconTool):
    """Minimal compliant tool used purely for contract testing."""

    name   = "ContractDummy"
    binary = ""           # no external binary

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        return [
            self._make_result(t, data={"found": [f"sub.{t}"]})
            for t in targets
        ]

    def is_installed(self) -> bool:
        return True       # no binary required


def test_registration() -> None:
    """Tool must appear in REGISTRY after decoration."""
    assert REGISTRY.is_registered(_ContractDummyTool), "Tool not in registry"
    stage = REGISTRY.stage_for_tool(_ContractDummyTool)
    assert stage == Stage.SUBDOMAIN_ENUM, f"Wrong stage: {stage}"
    classes = REGISTRY.tools_for_stage(Stage.SUBDOMAIN_ENUM)
    assert _ContractDummyTool in classes, "Class missing from stage bucket"
    print("  [PASS] clause 2 — tool registered, stage stamped, bucket populated")


def test_idempotent_registration() -> None:
    """Importing / decorating twice must NOT create duplicates."""
    count_before = len(REGISTRY.tools_for_stage(Stage.SUBDOMAIN_ENUM))
    # Simulate re-import by re-applying the decorator
    register_tool(stage=Stage.SUBDOMAIN_ENUM)(_ContractDummyTool)
    count_after = len(REGISTRY.tools_for_stage(Stage.SUBDOMAIN_ENUM))
    assert count_before == count_after, (
        f"Duplicate registration! before={count_before} after={count_after}"
    )
    print("  [PASS] clause 2b — idempotent registration (no duplicates)")


# ===========================================================================
# CONTRACT CLAUSE 3
# run() MUST be a coroutine (async def).
# ===========================================================================

def test_run_is_coroutine() -> None:
    """run() must be defined with ``async def``."""
    method = getattr(_ContractDummyTool, "run")
    assert asyncio.iscoroutinefunction(method), "run() is not async"
    print("  [PASS] clause 3 — run() is a coroutine function")


# ===========================================================================
# CONTRACT CLAUSE 4
# run() MUST return List[ReconResult], never None.
# ===========================================================================

def test_run_returns_list_of_reconresult() -> None:
    """run() must return a non-None list of ReconResult objects."""
    tool  = _ContractDummyTool()
    state = _make_state()
    results = asyncio.get_event_loop().run_until_complete(
        tool.run(["example.com"], state)
    )
    assert results is not None, "run() returned None"
    assert isinstance(results, list), f"run() returned {type(results)}, expected list"
    assert len(results) > 0, "run() returned empty list for non-empty targets"
    for r in results:
        assert isinstance(r, ReconResult), f"Item is {type(r)}, not ReconResult"
    print(f"  [PASS] clause 4 — run() returned {len(results)} ReconResult(s)")


# ===========================================================================
# CONTRACT CLAUSE 5
# ReconResult fields must match spec (tool, stage, target, success, data).
# ===========================================================================

def test_reconresult_fields() -> None:
    """Each ReconResult must carry correct tool, stage, and target."""
    tool   = _ContractDummyTool()
    state  = _make_state()
    result = asyncio.get_event_loop().run_until_complete(
        tool.run(["example.com"], state)
    )[0]

    assert result.tool   == "ContractDummy",        f"Wrong tool: {result.tool}"
    assert result.stage  == Stage.SUBDOMAIN_ENUM,   f"Wrong stage: {result.stage}"
    assert result.target == "example.com",           f"Wrong target: {result.target}"
    assert result.success is True,                   "success should be True"
    assert isinstance(result.data, dict),            f"data is {type(result.data)}"
    assert result.timestamp is not None,             "timestamp must be set"
    print("  [PASS] clause 5 — ReconResult fields match spec")


# ===========================================================================
# CONTRACT CLAUSE 6
# is_installed() MUST return bool, MUST NOT raise.
# ===========================================================================

def test_is_installed_returns_bool() -> None:
    """is_installed() must return a plain bool without raising."""
    tool = _ContractDummyTool()
    result = tool.is_installed()
    assert isinstance(result, bool), f"is_installed() returned {type(result)}"
    print(f"  [PASS] clause 6 — is_installed() returned bool ({result})")


# ===========================================================================
# CONTRACT CLAUSE 7
# Tool with missing binary must return False from is_installed().
# ===========================================================================

@register_tool(stage=Stage.PORT_SCAN)
class _MissingBinaryTool(ReconTool):
    """Simulates a tool whose binary is not installed."""
    name   = "MissingBinaryTool"
    binary = "__binary_that_will_never_exist_xyzzy__"

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        return []  # StageRunner skips us before calling run()

    def is_installed(self) -> bool:
        return self._check_binary()   # uses ReconTool._check_binary()


def test_missing_binary_not_installed() -> None:
    """_check_binary() must return False for a nonexistent binary."""
    tool = _MissingBinaryTool()
    assert tool.is_installed() is False, "Expected False for missing binary"
    print("  [PASS] clause 7 -- missing binary -> is_installed() is False")


# ===========================================================================
# CONTRACT CLAUSE 8
# run() MUST catch all exceptions — never propagate out.
# ===========================================================================

@register_tool(stage=Stage.DNS_RESOLUTION)
class _ExplodingTool(ReconTool):
    """Tool that simulates an internal crash — must not propagate."""
    name   = "ExplodingTool"
    binary = ""

    async def run(self, targets: List[str], state: PipelineState) -> List[ReconResult]:
        results = []
        for target in targets:
            try:
                raise RuntimeError("Simulated tool crash")
            except Exception as exc:
                results.append(ReconResult.failure(
                    tool=self.tool_name,
                    stage=self.stage or Stage.DNS_RESOLUTION,
                    target=target,
                    error=str(exc),
                ))
        return results

    def is_installed(self) -> bool:
        return True


def test_run_catches_exceptions() -> None:
    """A crashing tool must return ReconResult.failure, not propagate."""
    tool  = _ExplodingTool()
    state = _make_state()
    results = asyncio.get_event_loop().run_until_complete(
        tool.run(["example.com"], state)
    )
    assert len(results) == 1
    r = results[0]
    assert r.success is False,              "success should be False after crash"
    assert "Simulated tool crash" in r.error, f"Wrong error: {r.error}"
    assert r.stage  == Stage.DNS_RESOLUTION, f"Stage mismatch: {r.stage}"
    print("  [PASS] clause 8 — exception contained, ReconResult.failure returned")


# ===========================================================================
# CONTRACT CLAUSE 9
# ReconTool is abstract — cannot be instantiated directly.
# ===========================================================================

def test_abstract_base_not_instantiable() -> None:
    """ReconTool itself must be abstract and raise TypeError on instantiation."""
    try:
        ReconTool()  # type: ignore[abstract]
        assert False, "Should have raised TypeError"
    except TypeError:
        pass
    print("  [PASS] clause 9 — ReconTool is abstract, cannot be instantiated")


# ===========================================================================
# CONTRACT CLAUSE 10
# Auto-discovery via discover_tools() must not crash even with no plugins.
# ===========================================================================

def test_discover_tools_no_crash() -> None:
    """
    discover_tools() must handle an empty tools/ tree without crashing.
    We run it against the real package (all stub __init__ files, no plugins yet).
    """
    count = discover_tools("recon_node.tools")
    assert isinstance(count, int) and count >= 0, f"Bad return: {count}"
    print(f"  [PASS] clause 10 — discover_tools() completed, {count} module(s) found")


# ===========================================================================
# CONTRACT CLAUSE 11
# _stage class attribute is set by @register_tool, readable on instance.
# ===========================================================================

def test_stage_attribute_on_instance() -> None:
    """tool.stage must return the Stage registered by @register_tool."""
    tool = _ContractDummyTool()
    assert tool.stage == Stage.SUBDOMAIN_ENUM, f"tool.stage = {tool.stage}"
    print("  [PASS] clause 11 — tool.stage accessible from instance")


# ===========================================================================
# CONTRACT CLAUSE 12
# tool_name falls back to class name when name = ''.
# ===========================================================================

@register_tool(stage=Stage.HTTP_PROBE)
class _NoNameTool(ReconTool):
    """Tool with empty name — must fall back to class name."""
    name   = ""
    binary = ""

    async def run(self, targets, state):
        return []

    def is_installed(self):
        return True


def test_tool_name_fallback() -> None:
    """tool_name must return class __name__ when name = ''."""
    tool = _NoNameTool()
    assert tool.tool_name == "_NoNameTool", f"tool_name = {tool.tool_name!r}"
    print("  [PASS] clause 12 — tool_name falls back to class name")


# ===========================================================================
# CONTRACT CLAUSE 13
# _make_result() produces a valid ReconResult with correct tool/stage/target.
# ===========================================================================

def test_make_result_helper() -> None:
    """_make_result() must return a well-formed ReconResult."""
    tool   = _ContractDummyTool()
    result = tool._make_result("api.example.com", data={"foo": "bar"})
    assert isinstance(result, ReconResult)
    assert result.tool    == "ContractDummy"
    assert result.stage   == Stage.SUBDOMAIN_ENUM
    assert result.target  == "api.example.com"
    assert result.success is True
    assert result.data    == {"foo": "bar"}
    print("  [PASS] clause 13 — _make_result() produces valid ReconResult")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_subclass_enforcement,
        test_registration,
        test_idempotent_registration,
        test_run_is_coroutine,
        test_run_returns_list_of_reconresult,
        test_reconresult_fields,
        test_is_installed_returns_bool,
        test_missing_binary_not_installed,
        test_run_catches_exceptions,
        test_abstract_base_not_instantiable,
        test_discover_tools_no_crash,
        test_stage_attribute_on_instance,
        test_tool_name_fallback,
        test_make_result_helper,
    ]

    passed = failed = 0
    print(f"\n{'='*60}")
    print("  Plugin Contract Conformance Tests")
    print(f"{'='*60}")

    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {fn.__name__}: {exc}")
            failed += 1

    print(f"{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'='*60}\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
