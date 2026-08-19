"""
tools/base.py
~~~~~~~~~~~~~
Plugin contract for every recon tool.

HOW TO ADD A NEW TOOL (plug-and-play contract)
===============================================
1. Create a new .py file inside tools/<stage>/ (e.g. tools/subdomain/myfinder.py)
2. Subclass ``ReconTool``
3. Decorate the class with ``@register_tool(stage=Stage.SUBDOMAIN_ENUM)``
4. Implement the two required methods:

       async def run(
           self,
           targets: List[str],
           state: PipelineState,
       ) -> List[ReconResult]:
           ...

       def is_installed(self) -> bool:
           return shutil.which("mybinary") is not None

5. Drop the file — nothing else changes.  The tool is automatically discovered
   and wired into that stage's execution on the next pipeline run.

IMPORTANT INVARIANTS
--------------------
- ``run()`` MUST be a coroutine (``async def``).
- ``run()`` MUST return a (possibly empty) ``List[ReconResult]`` — never None.
- ``run()`` MUST NOT raise — catch all exceptions internally and return a
  ``ReconResult.failure(...)`` instead.
- ``is_installed()`` MUST NOT make network calls or run subprocesses —
  only ``shutil.which()`` / ``pathlib.Path.exists()``.
- A tool whose ``is_installed()`` returns False is silently skipped by
  ``StageRunner`` with a WARNING log — the pipeline continues.
"""

from __future__ import annotations

import abc
import asyncio
import importlib
import importlib.util
import logging
import pkgutil
import shutil
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Type

from recon_node.models import PipelineState, ReconResult, Stage

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

class _ToolRegistry:
    """
    Singleton registry that maps each Stage to the list of ReconTool *classes*
    registered for it.

    Tool classes are added via the ``@register_tool`` decorator — you never
    call this class directly.
    """

    def __init__(self) -> None:
        # Stage.value (str) → list of ReconTool subclasses
        self._registry: Dict[str, List[Type[ReconTool]]] = {}

    # ------------------------------------------------------------------
    # Internal (used by @register_tool)
    # ------------------------------------------------------------------

    def _register(self, stage: Stage, tool_cls: Type["ReconTool"]) -> None:
        key = stage.value
        if key not in self._registry:
            self._registry[key] = []
        if tool_cls not in self._registry[key]:          # idempotent
            self._registry[key].append(tool_cls)
            log.debug("Registered tool %s → stage %s", tool_cls.__name__, key)

    # ------------------------------------------------------------------
    # Public query API (used by StageRunner)
    # ------------------------------------------------------------------

    def tools_for_stage(self, stage: Stage) -> List[Type["ReconTool"]]:
        """Return all tool *classes* registered for a given stage."""
        return list(self._registry.get(stage.value, []))

    def all_stages(self) -> List[Stage]:
        """Return all stages that have at least one registered tool."""
        return [Stage(k) for k in self._registry if self._registry[k]]

    def registered_tool_names(self, stage: Optional[Stage] = None) -> List[str]:
        """Return class names of registered tools, optionally filtered by stage."""
        if stage is not None:
            return [cls.__name__ for cls in self.tools_for_stage(stage)]
        names: List[str] = []
        for cls_list in self._registry.values():
            names.extend(c.__name__ for c in cls_list)
        return names

    def is_registered(self, tool_cls: Type["ReconTool"]) -> bool:
        """Return True if this class is in the registry under any stage."""
        for cls_list in self._registry.values():
            if tool_cls in cls_list:
                return True
        return False

    def stage_for_tool(self, tool_cls: Type["ReconTool"]) -> Optional[Stage]:
        """Return the Stage a tool class is registered under, or None."""
        for stage_key, cls_list in self._registry.items():
            if tool_cls in cls_list:
                return Stage(stage_key)
        return None

    def __repr__(self) -> str:  # pragma: no cover
        lines = [f"ToolRegistry({len(self.registered_tool_names())} tools):"]
        for stage in Stage.ordered():
            tools = self.tools_for_stage(stage)
            if tools:
                names = ", ".join(c.__name__ for c in tools)
                lines.append(f"  {stage.value:20s} → [{names}]")
        return "\n".join(lines)


# Module-level singleton — import this in StageRunner and tests
REGISTRY = _ToolRegistry()


# ---------------------------------------------------------------------------
# @register_tool decorator
# ---------------------------------------------------------------------------

def register_tool(stage: Stage):
    """
    Class decorator that registers a ``ReconTool`` subclass into the global
    ``REGISTRY`` for the specified pipeline stage.

    Usage::

        @register_tool(stage=Stage.SUBDOMAIN_ENUM)
        class SubfinderTool(ReconTool):
            ...

    The decorator returns the class unchanged so it remains fully usable as
    a normal Python class.
    """
    def decorator(cls: Type["ReconTool"]) -> Type["ReconTool"]:
        if not (isinstance(cls, type) and issubclass(cls, ReconTool)):
            raise TypeError(
                f"@register_tool can only decorate ReconTool subclasses, got {cls!r}"
            )
        # Stamp the stage onto the class so it can be read without the registry
        cls._stage = stage  # type: ignore[attr-defined]
        REGISTRY._register(stage, cls)
        return cls
    return decorator


# ---------------------------------------------------------------------------
# ReconTool Abstract Base Class
# ---------------------------------------------------------------------------

class ReconTool(abc.ABC):
    """
    Abstract base class for every recon tool plugin.

    Subclass this, implement the two abstract methods, and apply the
    ``@register_tool`` decorator.  ``StageRunner`` will handle the rest.

    Class Attributes
    ----------------
    name : str
        Human-readable name for the tool.  Defaults to the class name.
        Override to customise.
    binary : str
        Name of the external binary as it appears on PATH (e.g. 'subfinder').
        Used as the default implementation of ``is_installed()``.
        Set to '' if the tool has no external binary dependency.
    timeout : int
        Maximum seconds to wait for a single tool invocation.
        Default is 300 (5 minutes).  Override per-tool as needed.
    _stage : Stage
        Set automatically by ``@register_tool``.  Do not set manually.
    """

    # Class-level attributes — override in subclasses ----------------------
    name:    ClassVar[str] = ""     # falls back to cls.__name__ if empty
    binary:  ClassVar[str] = ""     # binary name for is_installed() default
    timeout: ClassVar[int] = 300    # seconds

    # Set by @register_tool ------------------------------------------------
    _stage: ClassVar[Optional[Stage]] = None

    # ------------------------------------------------------------------
    # Abstract interface — MUST implement in every subclass
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def run(
        self,
        targets: List[str],
        state: PipelineState,
    ) -> List[ReconResult]:
        """
        Execute this tool against the given targets.

        Parameters
        ----------
        targets:
            List of target strings appropriate for this stage.
            - SUBDOMAIN_ENUM → root domains (e.g. ["example.com"])
            - DNS_RESOLUTION → subdomain FQDNs
            - HTTP_PROBE     → subdomain FQDNs (StageRunner prepends scheme)
            - PORT_SCAN      → live host FQDNs / IPs
            - URL_DISCOVERY  → live host base URLs
            - FINGERPRINT    → live host base URLs
        state:
            The live PipelineState.  Read from it; write back via its helper
            methods (``upsert_subdomain``, ``add_stage_results``, etc.).

        Returns
        -------
        List[ReconResult]
            One result per target attempted.  Must never return None.
            On partial failure, return a mix of successful and failed results.
        """

    @abc.abstractmethod
    def is_installed(self) -> bool:
        """
        Return True if this tool's external binary is present on the system.

        - Use ``shutil.which(self.binary)`` for standard PATH checks.
        - Use ``pathlib.Path(path).exists()`` for absolute paths.
        - NEVER make network calls or run subprocesses here.
        - If the tool has no external binary, return True unconditionally.
        """

    # ------------------------------------------------------------------
    # Provided helpers — available to all subclasses
    # ------------------------------------------------------------------

    @property
    def tool_name(self) -> str:
        """Canonical name used in ReconResult.tool and log messages."""
        return self.name or self.__class__.__name__

    @property
    def stage(self) -> Optional[Stage]:
        """The stage this tool is registered under (set by @register_tool)."""
        return self.__class__._stage

    def _check_binary(self, binary: Optional[str] = None) -> bool:
        """Shared ``is_installed`` implementation: ``shutil.which`` lookup."""
        b = binary or self.binary
        if not b:
            return True   # no binary required
        return shutil.which(b) is not None

    async def _run_subprocess(
        self,
        cmd: List[str],
        *,
        timeout: Optional[int] = None,
        stdin_data: Optional[bytes] = None,
    ) -> tuple[int, str, str]:
        """
        Run an external command asynchronously.

        Returns (returncode, stdout, stderr).
        Never raises — timeout and OS errors are caught and returned as
        returncode=-1 with the error message in stderr.
        """
        effective_timeout = timeout or self.timeout
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(input=stdin_data),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return -1, "", f"[timeout after {effective_timeout}s]"

            return (
                proc.returncode or 0,
                stdout_b.decode("utf-8", errors="replace"),
                stderr_b.decode("utf-8", errors="replace"),
            )
        except FileNotFoundError:
            return -1, "", f"[binary not found: {cmd[0]}]"
        except OSError as exc:
            return -1, "", f"[OSError: {exc}]"

    def _make_result(
        self,
        target: str,
        data: dict,
        raw_output: str = "",
        *,
        success: bool = True,
        error: Optional[str] = None,
    ) -> ReconResult:
        """
        Convenience factory — creates a ReconResult pre-filled with this
        tool's name and registered stage.
        """
        return ReconResult(
            tool=self.tool_name,
            stage=self.stage or Stage.OUTPUT,   # fallback; should never happen
            target=target,
            data=data,
            raw_output=raw_output,
            success=success,
            error=error,
        )

    def __repr__(self) -> str:  # pragma: no cover
        installed = "✓" if self.is_installed() else "✗"
        return f"<{self.__class__.__name__} stage={self.stage} binary={self.binary!r} installed={installed}>"


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------

def discover_tools(tools_package: str = "recon_node.tools") -> int:
    """
    Walk the ``tools/`` sub-packages and import every module found.

    Importing a module that contains a ``@register_tool``-decorated class
    causes that class to self-register into ``REGISTRY``.  No manual wiring
    is required.

    Parameters
    ----------
    tools_package:
        Dotted package name of the tools directory.  Override in tests.

    Returns
    -------
    int
        Number of modules successfully imported.
    """
    try:
        pkg = importlib.import_module(tools_package)
    except ModuleNotFoundError:
        log.warning("tools package '%s' not found — skipping discovery", tools_package)
        return 0

    pkg_path = getattr(pkg, "__path__", [])
    imported = 0

    for finder, module_name, is_pkg in pkgutil.walk_packages(
        path=pkg_path,
        prefix=tools_package + ".",
        onerror=lambda name: log.warning("Error scanning module %s", name),
    ):
        # Skip __init__ files and the base module itself
        if module_name.endswith((".__init__", ".base")):
            continue
        try:
            importlib.import_module(module_name)
            imported += 1
            log.debug("Discovered tool module: %s", module_name)
        except Exception as exc:
            log.warning("Failed to import tool module %s: %s", module_name, exc)

    log.info("Tool discovery complete: %d modules loaded, %d tools registered",
             imported, len(REGISTRY.registered_tool_names()))
    return imported
