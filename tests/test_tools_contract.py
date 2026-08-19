"""
tests/test_tools_contract.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Conformance test for ALL tool implementations against the ReconTool plugin
contract defined in tools/base.py.

This test imports every tool module, verifies:
1. Class inherits from ReconTool
2. Decorated with @register_tool (has _stage, is in REGISTRY)
3. run() is a coroutine (async def)
4. is_installed() returns a bool, never raises
5. name, binary, timeout class attributes are well-formed
6. tool_name property returns a non-empty string
7. _make_result() produces a valid ReconResult
8. Multiple tools per stage register without collision

NO real binaries are required — we only check the code structure and
contract compliance.  We do NOT call run() since that needs real binaries.

Run:
    $env:PYTHONPATH = "<repo-root>"
    .venv/Scripts/python tests/test_tools_contract.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from typing import List, Type

# ---------------------------------------------------------------------------
# Bootstrap — discover all tools
# ---------------------------------------------------------------------------

def _bootstrap():
    from recon_node.tools.base import discover_tools
    discover_tools()

_bootstrap()

from recon_node.models import ReconResult, Stage
from recon_node.tools.base import REGISTRY, ReconTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_tool_classes() -> List[Type[ReconTool]]:
    """Return all registered tool classes across all stages."""
    classes: List[Type[ReconTool]] = []
    for stage in Stage.ordered():
        classes.extend(REGISTRY.tools_for_stage(stage))
    return classes


# ===========================================================================
# CLAUSE 1 — All expected tools are discovered and registered
# ===========================================================================

EXPECTED_TOOLS = {
    Stage.SUBDOMAIN_ENUM: ["SubfinderTool", "AssetfinderTool", "AmassTool", "GotatorTool"],
    Stage.DNS_RESOLUTION: ["PurednsTool", "DnsxTool"],
    Stage.HTTP_PROBE:     ["HttpxTool"],
    Stage.PORT_SCAN:      ["NaabuTool", "NmapTool"],
    Stage.URL_DISCOVERY:  ["GauTool", "WaybackurlsTool", "KatanaTool"],
    Stage.FINGERPRINT:    ["GowitnessTool", "NucleiReconTool"],
}


def test_all_tools_discovered() -> None:
    """Every expected tool must be registered in REGISTRY after discover_tools()."""
    all_names = REGISTRY.registered_tool_names()
    missing = []
    for stage, expected_names in EXPECTED_TOOLS.items():
        stage_names = REGISTRY.registered_tool_names(stage)
        for name in expected_names:
            if name not in stage_names:
                missing.append(f"{name} -> {stage.value}")
    assert not missing, f"Missing tools: {missing}"
    print(f"  [PASS] clause 1 -- {len(all_names)} tools discovered across "
          f"{len(EXPECTED_TOOLS)} stages")


# ===========================================================================
# CLAUSE 2 — Every tool class inherits from ReconTool
# ===========================================================================

def test_all_inherit_recon_tool() -> None:
    """Every registered tool must be a subclass of ReconTool."""
    for cls in _all_tool_classes():
        assert issubclass(cls, ReconTool), f"{cls.__name__} does not inherit ReconTool"
    print(f"  [PASS] clause 2 -- {len(_all_tool_classes())} tools inherit ReconTool")


# ===========================================================================
# CLAUSE 3 — _stage attribute stamped by @register_tool
# ===========================================================================

def test_stage_attribute_stamped() -> None:
    """Each tool must have a _stage ClassVar set by @register_tool."""
    for cls in _all_tool_classes():
        assert hasattr(cls, "_stage"), f"{cls.__name__} missing _stage"
        assert isinstance(cls._stage, Stage), \
            f"{cls.__name__}._stage is {type(cls._stage)}, expected Stage"
        # Verify registry agrees
        reg_stage = REGISTRY.stage_for_tool(cls)
        assert reg_stage == cls._stage, \
            f"{cls.__name__}: _stage={cls._stage} but registry says {reg_stage}"
    print(f"  [PASS] clause 3 -- _stage attribute correct for all {len(_all_tool_classes())} tools")


# ===========================================================================
# CLAUSE 4 — run() is a coroutine (async def)
# ===========================================================================

def test_run_is_coroutine() -> None:
    """run() must be an async method on every tool."""
    for cls in _all_tool_classes():
        assert inspect.iscoroutinefunction(cls.run), \
            f"{cls.__name__}.run() is not async"
    print(f"  [PASS] clause 4 -- run() is async for all {len(_all_tool_classes())} tools")


# ===========================================================================
# CLAUSE 5 — is_installed() returns bool, never raises
# ===========================================================================

def test_is_installed_returns_bool() -> None:
    """is_installed() must return bool and never raise."""
    for cls in _all_tool_classes():
        tool = cls()
        try:
            result = tool.is_installed()
        except Exception as exc:
            assert False, f"{cls.__name__}.is_installed() raised: {exc}"
        assert isinstance(result, bool), \
            f"{cls.__name__}.is_installed() returned {type(result)}, expected bool"
    print(f"  [PASS] clause 5 -- is_installed() returns bool for all tools")


# ===========================================================================
# CLAUSE 6 — name class attribute is a non-empty string
# ===========================================================================

def test_name_attribute() -> None:
    """Each tool must have a non-empty name (explicit or via __name__)."""
    for cls in _all_tool_classes():
        tool = cls()
        assert tool.tool_name, f"{cls.__name__}.tool_name is empty"
        assert isinstance(tool.tool_name, str)
    print(f"  [PASS] clause 6 -- tool_name is non-empty string for all tools")


# ===========================================================================
# CLAUSE 7 — binary class attribute is a string
# ===========================================================================

def test_binary_attribute() -> None:
    """Each tool must have a binary class attribute (string)."""
    for cls in _all_tool_classes():
        assert isinstance(cls.binary, str), \
            f"{cls.__name__}.binary is {type(cls.binary)}"
    print(f"  [PASS] clause 7 -- binary is str for all tools")


# ===========================================================================
# CLAUSE 8 — timeout is a positive integer
# ===========================================================================

def test_timeout_attribute() -> None:
    """Each tool must have a timeout > 0."""
    for cls in _all_tool_classes():
        assert isinstance(cls.timeout, int), \
            f"{cls.__name__}.timeout is {type(cls.timeout)}"
        assert cls.timeout > 0, f"{cls.__name__}.timeout={cls.timeout}"
    print(f"  [PASS] clause 8 -- timeout is positive int for all tools")


# ===========================================================================
# CLAUSE 9 — _make_result() produces valid ReconResult
# ===========================================================================

def test_make_result_factory() -> None:
    """_make_result() must produce a ReconResult with correct tool/stage."""
    for cls in _all_tool_classes():
        tool = cls()
        result = tool._make_result("example.com", {"key": "value"}, "raw output")
        assert isinstance(result, ReconResult), \
            f"{cls.__name__}._make_result() returned {type(result)}"
        assert result.tool == tool.tool_name
        assert result.stage == cls._stage
        assert result.target == "example.com"
        assert result.data == {"key": "value"}
        assert result.success is True
    print(f"  [PASS] clause 9 -- _make_result() works for all tools")


# ===========================================================================
# CLAUSE 10 — _make_result() failure mode
# ===========================================================================

def test_make_result_failure() -> None:
    """_make_result(success=False, error=...) must set failure fields."""
    for cls in _all_tool_classes():
        tool = cls()
        result = tool._make_result(
            "example.com", {}, success=False, error="test error"
        )
        assert result.success is False
        assert result.error == "test error"
    print(f"  [PASS] clause 10 -- _make_result() failure mode works for all tools")


# ===========================================================================
# CLAUSE 11 — Multiple tools per stage register without collision
# ===========================================================================

def test_no_stage_collision() -> None:
    """Multiple tools per stage must all be individually accessible."""
    for stage, expected in EXPECTED_TOOLS.items():
        registered = REGISTRY.registered_tool_names(stage)
        for name in expected:
            assert name in registered, \
                f"{name} missing from {stage.value} (got: {registered})"
    print(f"  [PASS] clause 11 -- no stage registration collisions")


# ===========================================================================
# CLAUSE 12 — stage property matches _stage
# ===========================================================================

def test_stage_property() -> None:
    """Instance .stage property must return the registered _stage."""
    for cls in _all_tool_classes():
        tool = cls()
        assert tool.stage == cls._stage, \
            f"{cls.__name__}: .stage={tool.stage} != ._stage={cls._stage}"
    print(f"  [PASS] clause 12 -- .stage property correct for all tools")


# ===========================================================================
# CLAUSE 13 — run() signature matches contract (targets, state)
# ===========================================================================

def test_run_signature() -> None:
    """run(self, targets, state) must accept exactly those params."""
    for cls in _all_tool_classes():
        sig = inspect.signature(cls.run)
        params = list(sig.parameters.keys())
        assert "self" in params, f"{cls.__name__}.run() missing 'self'"
        assert "targets" in params, f"{cls.__name__}.run() missing 'targets'"
        assert "state" in params, f"{cls.__name__}.run() missing 'state'"
    print(f"  [PASS] clause 13 -- run() signature correct for all tools")


# ===========================================================================
# CLAUSE 14 — is_installed() signature matches contract ()
# ===========================================================================

def test_is_installed_signature() -> None:
    """is_installed(self) must accept only self."""
    for cls in _all_tool_classes():
        sig = inspect.signature(cls.is_installed)
        params = [p for p in sig.parameters.keys() if p != "self"]
        assert len(params) == 0, \
            f"{cls.__name__}.is_installed() has unexpected params: {params}"
    print(f"  [PASS] clause 14 -- is_installed() signature correct for all tools")


# ===========================================================================
# CLAUSE 15 — Each tool has a unique name within its stage
# ===========================================================================

def test_unique_names_per_stage() -> None:
    """No two tools in the same stage may share the same tool_name."""
    for stage in Stage.ordered():
        classes = REGISTRY.tools_for_stage(stage)
        names = [cls().tool_name for cls in classes]
        assert len(names) == len(set(names)), \
            f"Duplicate tool names in {stage.value}: {names}"
    print(f"  [PASS] clause 15 -- unique tool_name per stage")


# ===========================================================================
# CLAUSE 16 — Binary names match expected values
# ===========================================================================

EXPECTED_BINARIES = {
    "SubfinderTool":    "subfinder",
    "AssetfinderTool":  "assetfinder",
    "AmassTool":        "amass",
    "GotatorTool":      "gotator",
    "PurednsTool":      "puredns",
    "DnsxTool":         "dnsx",
    "HttpxTool":        "httpx",
    "NaabuTool":        "naabu",
    "NmapTool":         "nmap",
    "GauTool":          "gau",
    "WaybackurlsTool":  "waybackurls",
    "KatanaTool":       "katana",
    "GowitnessTool":    "gowitness",
    "NucleiReconTool":  "nuclei",
}


def test_binary_names() -> None:
    """Each tool's binary must match the expected system binary name."""
    for cls in _all_tool_classes():
        expected = EXPECTED_BINARIES.get(cls.__name__)
        if expected is not None:
            assert cls.binary == expected, \
                f"{cls.__name__}.binary={cls.binary!r}, expected {expected!r}"
    print(f"  [PASS] clause 16 -- binary names match expectations")


# ===========================================================================
# Runner
# ===========================================================================

def run_all() -> None:
    tests = [
        test_all_tools_discovered,
        test_all_inherit_recon_tool,
        test_stage_attribute_stamped,
        test_run_is_coroutine,
        test_is_installed_returns_bool,
        test_name_attribute,
        test_binary_attribute,
        test_timeout_attribute,
        test_make_result_factory,
        test_make_result_failure,
        test_no_stage_collision,
        test_stage_property,
        test_run_signature,
        test_is_installed_signature,
        test_unique_names_per_stage,
        test_binary_names,
    ]

    passed = failed = 0
    print(f"\n{'='*62}")
    print("  Tool Implementation Contract Conformance Tests")
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
