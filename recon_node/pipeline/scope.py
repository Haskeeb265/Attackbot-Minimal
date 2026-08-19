"""
pipeline/scope.py
~~~~~~~~~~~~~~~~~
ScopeValidator — CRITICAL safety layer.

Every target is validated here before any active tool touches it.
Out-of-scope targets are logged and silently dropped. They are NEVER
passed to a tool.

CONTRACT
--------
- ``is_in_scope(target, scope_list) -> bool``
    Returns True only if ``target`` matches at least one pattern in ``scope_list``.

- Wildcard pattern ``*.example.com``
    Matches every subdomain at any depth (e.g. api.example.com,
    sub.api.example.com) but NOT the bare root domain ``example.com`` itself.

- Exact pattern ``api.example.com``
    Matches only that exact FQDN, case-insensitively.

- Root-domain pattern ``example.com`` (no wildcard prefix)
    Matches only ``example.com``, not its subdomains.

- Port-annotated targets ``api.example.com:443``
    Port suffix is stripped before matching.

- URL targets ``https://api.example.com/path?q=1``
    Scheme, path, and query are stripped; hostname is extracted and matched.

- Empty scope list → nothing passes (fail-closed safe default).

- All comparisons are case-insensitive.

- Invalid / unparseable targets → False (never crash, never allow).
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple
from urllib.parse import urlparse

log = logging.getLogger(__name__)


class ScopeValidator:
    """
    Stateless scope enforcement engine.

    Instantiate once at pipeline startup and pass to every ``StageRunner``.
    The instance carries no mutable state — it is safe to share across
    concurrent coroutines without any locking.

    Usage::

        validator = ScopeValidator(scope=["*.example.com", "api.example.com"])
        if validator.is_in_scope("sub.example.com"):
            ...

        # Or one-shot with an explicit scope list:
        ok = ScopeValidator.check("sub.example.com", ["*.example.com"])
    """

    def __init__(self, scope: List[str]) -> None:
        """
        Parameters
        ----------
        scope:
            List of in-scope patterns. Wildcards use the ``*.`` prefix.
            Example: ``["*.example.com", "api.partner.com"]``
        """
        self._scope: List[str] = [s.strip().lower() for s in scope if s.strip()]
        # Pre-split wildcard vs exact for O(1) per-pattern matching
        self._wildcards: List[str] = []   # stored WITHOUT the leading "*."
        self._exactes:   List[str] = []   # stored as-is (lowercased)

        for pattern in self._scope:
            if pattern.startswith("*."):
                self._wildcards.append(pattern[2:])   # "example.com"
            else:
                self._exactes.append(pattern)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_in_scope(self, target: str, scope_list: List[str] | None = None) -> bool:
        """
        Return True if ``target`` is covered by at least one scope pattern.

        ``scope_list`` is optional — if provided it overrides the instance's
        own scope (useful for one-shot checks without instantiation).

        This method never raises.  On any parsing error it returns False.
        """
        if scope_list is not None:
            return ScopeValidator(scope_list).is_in_scope(target)

        hostname = self._extract_hostname(target)
        if not hostname:
            log.debug("ScopeValidator: could not extract hostname from %r — denied", target)
            return False

        hostname = hostname.lower()

        # Exact match first (cheap)
        if hostname in self._exactes:
            log.debug("ScopeValidator: %r matched exact pattern", hostname)
            return True

        # Wildcard match
        for root in self._wildcards:
            if self._wildcard_match(hostname, root):
                log.debug("ScopeValidator: %r matched wildcard *.%s", hostname, root)
                return True

        log.debug("ScopeValidator: %r not in scope", hostname)
        return False

    def filter(
        self,
        targets: List[str],
    ) -> Tuple[List[str], List[str]]:
        """
        Partition ``targets`` into (in_scope, out_of_scope).

        The order within each list matches the input order.
        Out-of-scope entries are logged at DEBUG level.

        Returns
        -------
        in_scope : List[str]
            Targets that passed scope validation.
        out_of_scope : List[str]
            Targets that were rejected.
        """
        in_scope:     List[str] = []
        out_of_scope: List[str] = []

        for target in targets:
            if self.is_in_scope(target):
                in_scope.append(target)
            else:
                out_of_scope.append(target)
                log.warning(
                    "ScopeValidator: dropping out-of-scope target %r", target
                )

        return in_scope, out_of_scope

    # ------------------------------------------------------------------
    # Class-level convenience (no instantiation required)
    # ------------------------------------------------------------------

    @classmethod
    def check(cls, target: str, scope_list: List[str]) -> bool:
        """One-shot scope check without an instance."""
        return cls(scope_list).is_in_scope(target)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_hostname(target: str) -> str:
        """
        Extract the bare hostname from a target string.

        Handles:
        - Plain hostname:            ``api.example.com``
        - Port-annotated hostname:   ``api.example.com:443``
        - Full URL:                  ``https://api.example.com/path?q=1``
        - IPv4 address:              ``1.2.3.4``
        - IPv4 with port:            ``1.2.3.4:8080``

        Returns empty string on failure — never raises.
        """
        target = target.strip()
        if not target:
            return ""

        try:
            # If it looks like a URL (has a scheme), parse it properly
            if re.match(r"^[a-z][a-z0-9+\-.]*://", target, re.IGNORECASE):
                parsed = urlparse(target)
                return parsed.hostname or ""

            # Strip port suffix (e.g. api.example.com:443)
            # IPv6 addresses look like [::1]:8080 — handle separately
            if target.startswith("["):
                # IPv6
                bracket_end = target.find("]")
                if bracket_end != -1:
                    return target[1:bracket_end]
                return target

            # For everything else, split on ":" and take the first part
            return target.split(":")[0]

        except Exception as exc:
            log.debug("ScopeValidator._extract_hostname(%r) failed: %s", target, exc)
            return ""

    @staticmethod
    def _wildcard_match(hostname: str, root: str) -> bool:
        """
        Return True if ``hostname`` is a subdomain of ``root`` at any depth.

        ``root`` is the pattern AFTER stripping the leading ``*.``
        (e.g. ``"example.com"`` for the pattern ``"*.example.com"``).

        Rules:
        - ``hostname`` must end with ``"." + root``
        - ``hostname`` must NOT equal ``root`` itself (wildcards don't cover root)
        - At least one label must precede the root
        """
        suffix = "." + root
        return hostname.endswith(suffix) and hostname != root

    # ------------------------------------------------------------------
    # Introspection helpers (used in tests and logging)
    # ------------------------------------------------------------------

    @property
    def scope(self) -> List[str]:
        """Return the normalised scope list as stored internally."""
        return list(self._scope)

    @property
    def wildcard_roots(self) -> List[str]:
        """Return the root domains extracted from wildcard patterns."""
        return list(self._wildcards)

    @property
    def exact_patterns(self) -> List[str]:
        """Return the exact-match patterns."""
        return list(self._exactes)

    def describe(self) -> str:
        """Human-readable summary for log output."""
        return (
            f"ScopeValidator("
            f"wildcards={[f'*.{r}' for r in self._wildcards]}, "
            f"exact={self._exactes})"
        )

    def __repr__(self) -> str:
        return self.describe()
