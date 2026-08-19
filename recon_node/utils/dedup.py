"""
utils/dedup.py
~~~~~~~~~~~~~~
Deduplication utilities for subdomains and URLs.

CONTRACT
--------
deduplicate_subdomains(subdomains) -> List[Subdomain]
    Deduplicate Subdomain objects by FQDN (case-insensitive).
    Keeps the first occurrence.  Returns a new list.

deduplicate_urls(urls) -> List[str]
    Deduplicate URL strings by exact match.
    Preserves insertion order.  Returns a new list.

normalize_fqdn(fqdn) -> str
    Strip whitespace, lowercase, remove trailing dots.

normalize_url(url) -> str
    Strip whitespace, remove trailing slash, lowercase the scheme+host.
"""

from __future__ import annotations

from typing import List
from urllib.parse import urlparse, urlunparse

from recon_node.models import Subdomain


def normalize_fqdn(fqdn: str) -> str:
    """
    Normalize a fully-qualified domain name.

    - Strip whitespace
    - Lowercase
    - Remove trailing dots (DNS root label)
    - Remove scheme prefixes if accidentally present
    """
    fqdn = fqdn.strip().lower()
    for prefix in ("https://", "http://"):
        if fqdn.startswith(prefix):
            fqdn = fqdn[len(prefix):]
    fqdn = fqdn.split("/")[0]   # remove path
    fqdn = fqdn.split(":")[0]   # remove port
    fqdn = fqdn.rstrip(".")    # DNS root dot
    return fqdn


def normalize_url(url: str) -> str:
    """
    Normalize a URL for deduplication.

    - Strip whitespace
    - Lowercase scheme + host
    - Remove trailing slash from path
    - Preserve case of path/query/fragment
    """
    url = url.strip()
    try:
        parsed = urlparse(url)
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))
        return normalized
    except Exception:
        return url


def deduplicate_subdomains(subdomains: List[Subdomain]) -> List[Subdomain]:
    """
    Deduplicate Subdomain objects by normalized FQDN.

    Keeps the first occurrence of each FQDN.
    Returns a new list — does NOT modify the input.
    """
    seen: set[str] = set()
    result: List[Subdomain] = []
    for sd in subdomains:
        key = normalize_fqdn(sd.subdomain)
        if key not in seen:
            seen.add(key)
            result.append(sd)
    return result


def deduplicate_urls(urls: List[str]) -> List[str]:
    """
    Deduplicate URL strings.

    Uses normalized form for comparison but returns the original URL
    string.  Preserves insertion order.
    """
    seen: set[str] = set()
    result: List[str] = []
    for url in urls:
        key = normalize_url(url)
        if key not in seen:
            seen.add(key)
            result.append(url)
    return result
