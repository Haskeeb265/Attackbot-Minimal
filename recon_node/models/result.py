"""
models/result.py
~~~~~~~~~~~~~~~~
Core data models for the recon pipeline.

Every piece of data flowing through the pipeline is typed here.
Tools produce ReconResult objects; the aggregated view is Subdomain.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Stage Enum
# ---------------------------------------------------------------------------

class Stage(str, Enum):
    """Pipeline stages in execution order.

    Using ``str`` as the mixin ensures stage names serialize to plain strings
    in JSON / YAML keys without extra conversion steps.
    """

    SUBDOMAIN_ENUM = "subdomain_enum"
    DNS_RESOLUTION = "dns_resolution"
    HTTP_PROBE     = "http_probe"
    PORT_SCAN      = "port_scan"
    URL_DISCOVERY  = "url_discovery"
    FINGERPRINT    = "fingerprint"
    OUTPUT         = "output"

    # Convenience helpers ---------------------------------------------------

    @classmethod
    def ordered(cls) -> List["Stage"]:
        """Return stages in canonical pipeline execution order."""
        return [
            cls.SUBDOMAIN_ENUM,
            cls.DNS_RESOLUTION,
            cls.HTTP_PROBE,
            cls.PORT_SCAN,
            cls.URL_DISCOVERY,
            cls.FINGERPRINT,
            cls.OUTPUT,
        ]

    def next_stage(self) -> Optional["Stage"]:
        """Return the stage that follows this one, or None if this is last."""
        ordered = self.ordered()
        idx = ordered.index(self)
        return ordered[idx + 1] if idx + 1 < len(ordered) else None


# ---------------------------------------------------------------------------
# Port
# ---------------------------------------------------------------------------

class Port(BaseModel):
    """Represents a single open port discovered on a host."""

    port:     int            = Field(..., ge=1, le=65535, description="Port number")
    protocol: str            = Field(default="tcp",       description="Transport protocol (tcp/udp)")
    service:  Optional[str]  = Field(default=None,        description="Service name (e.g. 'http', 'ssh')")
    version:  Optional[str]  = Field(default=None,        description="Service version string")
    banner:   Optional[str]  = Field(default=None,        description="Raw banner grabbed from the port")
    state:    str            = Field(default="open",      description="Port state: open | filtered | closed")

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# HttpMetadata
# ---------------------------------------------------------------------------

class HttpMetadata(BaseModel):
    """HTTP-level metadata about a live host, populated by the HTTP_PROBE stage."""

    url:              str                    = Field(...,           description="Final URL after any redirects")
    status_code:      int                    = Field(...,           description="Final HTTP status code")
    title:            Optional[str]          = Field(default=None,  description="<title> tag content")
    technologies:     List[str]              = Field(default_factory=list,
                                                    description="Detected technology stack (e.g. nginx, React)")
    is_cdn:           bool                   = Field(default=False, description="Whether the host sits behind a CDN")
    cdn_name:         Optional[str]          = Field(default=None,  description="CDN provider name if detected")
    ip_address:       Optional[str]          = Field(default=None,  description="Resolved IP at probe time")
    redirect_chain:   List[str]              = Field(default_factory=list,
                                                    description="Ordered list of redirect URLs")
    content_length:   Optional[int]          = Field(default=None,  description="Content-Length header value")
    server:           Optional[str]          = Field(default=None,  description="Server header value")
    headers:          Dict[str, str]         = Field(default_factory=dict,
                                                    description="All response headers as key→value")
    screenshot_path:  Optional[str]          = Field(default=None,  description="Absolute path to screenshot file")

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# ReconResult
# ---------------------------------------------------------------------------

class ReconResult(BaseModel):
    """
    The atomic unit of output from any ReconTool.

    Each tool's ``run()`` method returns a list of ReconResult objects —
    one per target processed.  The ``data`` field carries tool-specific
    structured output; ``raw_output`` preserves the original stdout/stderr
    for debugging.
    """

    tool:        str              = Field(..., description="Tool class name (e.g. 'SubfinderTool')")
    stage:       Stage            = Field(..., description="Pipeline stage this result belongs to")
    target:      str              = Field(..., description="The specific target this result describes")
    timestamp:   datetime         = Field(
                                        default_factory=lambda: datetime.now(timezone.utc),
                                        description="UTC timestamp when the result was produced",
                                    )
    data:        Dict[str, Any]   = Field(default_factory=dict,
                                         description="Tool-specific structured output")
    raw_output:  str              = Field(default="",  description="Raw stdout / stderr from the tool")
    success:     bool             = Field(default=True, description="Whether the tool completed without error")
    error:       Optional[str]    = Field(default=None, description="Error message if success=False")

    model_config = {"frozen": False}

    # Convenience constructors ----------------------------------------------

    @classmethod
    def failure(
        cls,
        tool: str,
        stage: Stage,
        target: str,
        error: str,
        raw_output: str = "",
    ) -> "ReconResult":
        """Factory for a failed result — avoids repeating boilerplate in tool wrappers."""
        return cls(
            tool=tool,
            stage=stage,
            target=target,
            success=False,
            error=error,
            raw_output=raw_output,
        )


# ---------------------------------------------------------------------------
# Subdomain
# ---------------------------------------------------------------------------

class Subdomain(BaseModel):
    """
    Aggregated view of a single subdomain as it progresses through the pipeline.

    This model is enriched in-place at each stage:
      - SUBDOMAIN_ENUM  → subdomain + source
      - DNS_RESOLUTION  → ip_addresses added
      - HTTP_PROBE      → is_live + http_metadata
      - PORT_SCAN       → ports
      - URL_DISCOVERY   → urls
      - FINGERPRINT     → technologies + screenshot_path (via http_metadata)
    """

    subdomain:       str                       = Field(...,
                                                       description="Fully-qualified domain name")
    source:          str                       = Field(...,
                                                       description="Tool that first discovered this subdomain")
    ip_addresses:    List[str]                 = Field(default_factory=list,
                                                       description="Resolved IPv4/IPv6 addresses")
    cname:           Optional[str]             = Field(default=None,
                                                       description="CNAME target if the record is an alias")
    is_live:         bool                      = Field(default=False,
                                                       description="True if HTTP/HTTPS probe succeeded")
    in_scope:        bool                      = Field(default=True,
                                                       description="Scope validation result")
    http_metadata:   Optional[HttpMetadata]    = Field(default=None,
                                                       description="HTTP probe metadata (populated at HTTP_PROBE)")
    ports:           List[Port]                = Field(default_factory=list,
                                                       description="Open ports discovered at PORT_SCAN")
    urls:            List[str]                 = Field(default_factory=list,
                                                       description="URLs discovered at URL_DISCOVERY")
    technologies:    List[str]                 = Field(default_factory=list,
                                                       description="Technology fingerprints (de-duped)")
    screenshot_path: Optional[str]             = Field(default=None,
                                                       description="Path to Gowitness screenshot")
    tags:            List[str]                 = Field(default_factory=list,
                                                       description="Free-form labels (e.g. 'wildcard', 'cdn')")

    model_config = {"frozen": False}

    @field_validator("subdomain")
    @classmethod
    def normalise_subdomain(cls, v: str) -> str:
        """Strip whitespace and force lowercase for consistent deduplication."""
        return v.strip().lower()

    # Helpers ---------------------------------------------------------------

    def merge_technologies(self, new_techs: List[str]) -> None:
        """Add techs from a new source, deduplicating case-insensitively."""
        existing_lower = {t.lower() for t in self.technologies}
        for tech in new_techs:
            if tech.lower() not in existing_lower:
                self.technologies.append(tech)
                existing_lower.add(tech.lower())

    def add_urls(self, new_urls: List[str]) -> None:
        """Add URLs, deduplicating by exact string."""
        existing = set(self.urls)
        for url in new_urls:
            if url not in existing:
                self.urls.append(url)
                existing.add(url)
