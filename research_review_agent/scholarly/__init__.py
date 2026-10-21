"""Portable scholarly metadata discovery adapters and registry services."""

from .contracts import (
    IdentityMatch,
    MetadataResolution,
    PaperCandidate,
    PaperRecord,
    ProviderFailure,
    ProviderResponse,
    SearchRequest,
    SearchRun,
)
from .pipeline import ScholarlyDiscoveryPipeline

__all__ = [
    "IdentityMatch",
    "MetadataResolution",
    "PaperCandidate",
    "PaperRecord",
    "ProviderFailure",
    "ProviderResponse",
    "ScholarlyDiscoveryPipeline",
    "SearchRequest",
    "SearchRun",
]
