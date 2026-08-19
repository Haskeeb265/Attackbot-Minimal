"""
Canonical normalization (recon.md 5.3; IMPLEMENTATION_PLAN.md Stage 3).

Normalization here is *not* cosmetic: ``canonical_value`` is the graph's
unique-identity input (Stage 1's ``(asset_type, canonical_value)`` constraint),
so two spellings of the same asset MUST reduce to one canonical string or the
MERGE idempotency breaks.

Rules (spec): lowercase, strip trailing dot, IDNA/punycode non-ASCII hostnames,
canonicalize IP addresses (IPv6 compression), strip URL scheme default-ports and
fragments. Everything is stdlib-only and pure — no network, no infra — so the
whole stage is unit-testable in isolation.

Registrable-domain extraction uses a small, vendored multi-label public-suffix
set as a pragmatic interim. The plan's [OPEN] item is whether to adopt
``tldextract`` (full PSL) as a runtime dependency; until that's decided, this
heuristic covers the common cases and is the single place to swap in a real PSL.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

# Default ports stripped from canonical URLs.
_DEFAULT_PORTS = {"http": "80", "https": "443", "ftp": "21", "ws": "80", "wss": "443"}

# A conservative hostname charset check (labels of letters/digits/hyphen, plus
# underscore which appears in some DNS names like _dmarc).
_HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9_-]{1,63}(?:\.(?!-)[a-z0-9_-]{1,63})+$")

# Vendored multi-label public suffixes (INTERIM — see module docstring). Covers
# the common ccTLD second levels and a few well-known hosted zones so that
# registrable_domain() splits e.g. a.b.co.uk -> b.co.uk, not co.uk.
_MULTI_LABEL_SUFFIXES = frozenset({
    "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk", "ltd.uk", "plc.uk", "net.uk", "sch.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "id.au",
    "co.nz", "net.nz", "org.nz", "govt.nz",
    "co.jp", "or.jp", "ne.jp", "go.jp", "ac.jp",
    "com.br", "net.br", "org.br", "gov.br",
    "co.in", "net.in", "org.in", "gov.in", "ac.in",
    "com.cn", "net.cn", "org.cn", "gov.cn",
    "co.za", "org.za", "gov.za",
    "com.mx", "com.tr", "com.sg", "com.hk", "com.tw",
    "co.kr", "or.kr",
    # common hosted zones where the "registrable" unit is a label deeper
    "github.io", "gitlab.io", "s3.amazonaws.com", "herokuapp.com",
    "azurewebsites.net", "cloudfront.net", "web.app", "firebaseapp.com",
    "pages.dev", "workers.dev", "netlify.app", "vercel.app",
})


def _idna_label(label: str) -> str:
    """Best-effort punycode-encode a single hostname label; pass through on failure."""
    if label.isascii():
        return label
    try:
        return label.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return label


def normalize_hostname(raw: str) -> Optional[str]:
    """Reduce a raw token to a canonical hostname (or ``None`` if not a hostname).

    Handles bare hosts, ``*.example.com`` wildcards, ``https://host:443/path``
    URLs, userinfo, trailing dots and non-ASCII (punycode). Wildcards are
    reduced to their base domain here; callers that care about the wildcard flag
    should detect ``*.`` before calling.
    """
    if not raw:
        return None
    host = raw.strip().lower()
    if not host:
        return None
    host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", host)   # scheme
    host = host.split("/", 1)[0]                          # path/query
    host = host.split("@", 1)[-1]                         # userinfo
    host = host.split(":", 1)[0]                          # port
    host = host.lstrip("*.").rstrip(".")                  # wildcard + fqdn dot
    if not host or "." not in host or " " in host:
        return None
    host = ".".join(_idna_label(lbl) for lbl in host.split("."))
    if not _HOSTNAME_RE.match(host):
        return None
    return host


def is_wildcard(raw: str) -> bool:
    """True if the raw value is a ``*.`` wildcard domain."""
    return raw.strip().lower().lstrip().startswith("*.")


def normalize_ip(raw: str) -> Optional[str]:
    """Canonicalize an IPv4/IPv6 address (compressed form), or ``None``."""
    if not raw:
        return None
    try:
        return str(ipaddress.ip_address(raw.strip()))
    except ValueError:
        return None


def is_ip(raw: str) -> bool:
    return normalize_ip(raw) is not None


def normalize_url(raw: str) -> Optional[str]:
    """Canonicalize a URL: lowercase scheme+host, strip default port and
    fragment, keep path + query. Returns ``None`` if there is no usable host."""
    if not raw:
        return None
    parts = urlsplit(raw.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not host:
        return None
    host = ".".join(_idna_label(lbl) for lbl in host.rstrip(".").split("."))
    netloc = host
    if parts.port is not None and str(parts.port) != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{parts.port}"
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))  # fragment dropped


def url_host(raw: str) -> Optional[str]:
    """The canonical hostname of a URL (for the DERIVED_FROM domain pivot)."""
    parts = urlsplit(raw.strip())
    return normalize_hostname(parts.hostname) if parts.hostname else None


def url_endpoint(raw: str) -> Optional[str]:
    """Canonical ``host+path`` endpoint identity for a URL, or ``None``."""
    parts = urlsplit(raw.strip())
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return None
    path = parts.path or "/"
    return f"{host}{path}"


def registrable_domain(host: str) -> Optional[str]:
    """Registrable (apex) domain of a hostname using the vendored suffix set.

    INTERIM heuristic (see module docstring): checks the vendored multi-label
    suffixes first, else falls back to the last two labels. Swap in tldextract /
    a full PSL here if the [OPEN] dependency decision lands.
    """
    canon = normalize_hostname(host)
    if canon is None:
        return None
    labels = canon.split(".")
    for n in (3, 2):  # try 3-label suffix (a.co.uk), then 2-label (co.uk)
        if len(labels) > n and ".".join(labels[-n:]) in _MULTI_LABEL_SUFFIXES:
            return ".".join(labels[-(n + 1):])
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return canon


def content_hash(raw) -> str:
    """SHA-256 hex of a raw artifact (spec 5.3 content hash for dedup)."""
    data = raw.encode("utf-8", errors="replace") if isinstance(raw, str) else bytes(raw)
    return hashlib.sha256(data).hexdigest()
