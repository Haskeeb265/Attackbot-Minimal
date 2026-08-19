"""
Artifact extractors (recon.md 2/5.3; IMPLEMENTATION_PLAN.md Stage 3).

Turn raw text/artifacts (HTML, JS, API responses, certificate SAN lists) into
canonical :class:`Candidate` nodes. Deterministic regex/heuristic extraction —
pure, no network, no infra — so it is fixture-testable in isolation.

v1 extractor set (per the plan): hostnames, URLs (-> URL + host Domain +
Endpoint), IPs, certificate SANs, high-signal secrets (low confidence + flag,
never enough to trigger active work alone), and cloud-resource names.

Secrets are identified by a stable hash, not stored verbatim as the node
identity: ``canonical_value = "{kind}:{sha256(secret)[:16]}"`` with a redacted
preview in ``meta``. The graph is a shared system of record, so plaintext
secrets stay out of node identities/exports; the raw value lives only in
short-window raw retention (spec 5.3).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import normalize  # noqa: E402
from candidate import (  # noqa: E402
    TYPE_CLOUD_RESOURCE, TYPE_DOMAIN, TYPE_ENDPOINT, TYPE_IP, TYPE_SECRET,
    TYPE_URL, TYPE_WILDCARD, Candidate, dedupe,
)

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
_HOSTNAME_RE = re.compile(
    r"\b(?:[a-zA-Z0-9_](?:[a-zA-Z0-9_-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}\b"
)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# No \b anchors: IPv6 addresses can start/end with ':', where \b never fires.
# Loose match, then normalize_ip() validates (rejects times like 12:34:56).
_IPV6_RE = re.compile(r"(?<![:\w.])(?:[A-Fa-f0-9]{0,4}:){2,7}[A-Fa-f0-9]{0,4}(?![:\w])")
_URL_RE = re.compile(r"\bhttps?://[^\s\"'<>)\]}]+", re.IGNORECASE)

# Common file extensions that look like TLDs — rejected so "jquery.min.js" or
# "logo.png" are not mistaken for hostnames (INTERIM; a full PSL removes this).
_FILE_EXT_TLDS = frozenset({
    "js", "css", "html", "htm", "php", "asp", "aspx", "jsp", "json", "xml",
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "map", "txt",
    "md", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "csv", "zip", "gz",
    "woff", "woff2", "ttf", "eot", "mp4", "mp3", "webm", "wav", "py", "rb",
    "go", "ts", "tsx", "jsx", "sh", "yml", "yaml", "ini", "cfg", "lock",
})

# Secret signatures: (kind, compiled regex). Group 1 is the secret if present,
# else the whole match. Kept high-signal to limit noise (spec: secrets are noisy).
_SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,48}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("generic_api_key", re.compile(
        r"(?i)\b(?:api[_-]?key|apikey|access[_-]?token|secret[_-]?key|auth[_-]?token)\b"
        r"['\"\s:=]{1,4}([A-Za-z0-9_\-]{16,64})\b")),
]

# Cloud-resource signatures: (provider, regex with the resource name as group 1).
_CLOUD_PATTERNS = [
    ("aws_s3", re.compile(r"\bhttps?://([a-z0-9.\-]{3,63})\.s3[.a-z0-9-]*\.amazonaws\.com", re.I)),
    ("aws_s3", re.compile(r"\bhttps?://s3[.a-z0-9-]*\.amazonaws\.com/([a-z0-9.\-]{3,63})", re.I)),
    ("aws_s3", re.compile(r"\bs3://([a-z0-9.\-]{3,63})", re.I)),
    ("gcs", re.compile(r"\bhttps?://storage\.googleapis\.com/([a-z0-9._\-]{3,63})", re.I)),
    ("gcs", re.compile(r"\b([a-z0-9._\-]{3,63})\.storage\.googleapis\.com", re.I)),
    ("azure_blob", re.compile(r"\bhttps?://([a-z0-9]{3,24})\.blob\.core\.windows\.net", re.I)),
]

# Extraction confidences (observation confidence c_s fed to scoring later).
_CONF_HOST = 0.5
_CONF_IP = 0.6
_CONF_URL = 0.6
_CONF_ENDPOINT = 0.5
_CONF_SAN = 0.9
_CONF_SECRET = 0.3
_CONF_CLOUD = 0.6


# ---------------------------------------------------------------------------
# Individual extractors
# ---------------------------------------------------------------------------
def extract_hostnames(text: str) -> List[Candidate]:
    out: List[Candidate] = []
    for m in _HOSTNAME_RE.findall(text or ""):
        if m.rsplit(".", 1)[-1].lower() in _FILE_EXT_TLDS:
            continue
        host = normalize.normalize_hostname(m)
        if host:
            out.append(Candidate(TYPE_DOMAIN, host, _CONF_HOST))
    return dedupe(out)


def extract_ips(text: str) -> List[Candidate]:
    out: List[Candidate] = []
    for rx in (_IPV4_RE, _IPV6_RE):
        for m in rx.findall(text or ""):
            ip = normalize.normalize_ip(m)
            if ip:
                out.append(Candidate(TYPE_IP, ip, _CONF_IP))
    return dedupe(out)


def extract_urls(text: str) -> List[Candidate]:
    """URLs -> URL candidate + host Domain (DERIVED_FROM) + Endpoint (POINTS_TO)."""
    out: List[Candidate] = []
    for raw in _URL_RE.findall(text or ""):
        raw = raw.rstrip(".,;")
        url = normalize.normalize_url(raw)
        if not url:
            continue
        host = normalize.url_host(raw)
        out.append(Candidate(TYPE_URL, url, _CONF_URL, {"host": host}))
        if host:
            out.append(Candidate(TYPE_DOMAIN, host, _CONF_URL, {"via": "url"}))
        endpoint = normalize.url_endpoint(raw)
        if endpoint and not endpoint.endswith("/"):  # skip bare-host "/" endpoints
            out.append(Candidate(TYPE_ENDPOINT, endpoint, _CONF_ENDPOINT, {"host": host}))
    return dedupe(out)


def extract_cert_sans(sans: List[str]) -> List[Candidate]:
    """Certificate SAN list -> Domain / Wildcard candidates (high confidence)."""
    out: List[Candidate] = []
    for san in sans or []:
        host = normalize.normalize_hostname(san)
        if not host:
            continue
        if normalize.is_wildcard(san):
            out.append(Candidate(TYPE_WILDCARD, host, _CONF_SAN, {"wildcard": True}))
        else:
            out.append(Candidate(TYPE_DOMAIN, host, _CONF_SAN, {"via": "san"}))
    return dedupe(out)


def extract_secrets(text: str) -> List[Candidate]:
    out: List[Candidate] = []
    for kind, rx in _SECRET_PATTERNS:
        for m in rx.finditer(text or ""):
            secret = m.group(1) if m.groups() else m.group(0)
            if not secret:
                continue
            digest = normalize.content_hash(secret)[:16]
            preview = secret if len(secret) <= 8 else f"{secret[:4]}...{secret[-4:]}"
            out.append(Candidate(
                TYPE_SECRET, f"{kind}:{digest}", _CONF_SECRET,
                {"kind": kind, "preview": preview, "high_value": True},
            ))
    return dedupe(out)


def extract_cloud_resources(text: str) -> List[Candidate]:
    out: List[Candidate] = []
    for provider, rx in _CLOUD_PATTERNS:
        for name in rx.findall(text or ""):
            name = (name or "").lower().strip(".")
            if name:
                out.append(Candidate(
                    TYPE_CLOUD_RESOURCE, f"{provider}:{name}", _CONF_CLOUD,
                    {"provider": provider, "name": name},
                ))
    return dedupe(out)


def extract_all(text: str) -> List[Candidate]:
    """Run every text extractor and return one deduped candidate list.

    (SAN extraction is separate — it takes a structured list, not free text.)
    """
    combined: List[Candidate] = []
    combined += extract_urls(text)          # URLs first: seeds host + endpoint meta
    combined += extract_hostnames(text)
    combined += extract_ips(text)
    combined += extract_cloud_resources(text)
    combined += extract_secrets(text)
    return dedupe(combined)


def group_by_type(candidates: List[Candidate]) -> Dict[str, List[Candidate]]:
    """Convenience: bucket candidates by asset_type for reporting/tests."""
    grouped: Dict[str, List[Candidate]] = {}
    for c in candidates:
        grouped.setdefault(c.asset_type, []).append(c)
    return grouped
