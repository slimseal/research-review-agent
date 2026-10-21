"""Bounded subprocess PDF parsing; no script, attachment or external link execution."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

from .contracts import DocumentError

IMPLEMENTATION_VERSION = "rra-pages-1"


def parser_version() -> str:
    try:
        return f"pypdf-{importlib.metadata.version('pypdf')}+{IMPLEMENTATION_VERSION}"
    except importlib.metadata.PackageNotFoundError:
        raise DocumentError("PARSER_UNAVAILABLE", "Install the optional parser with: pip install 'research-review-agent[pdf]'. Core workflow remains usable.") from None


def run_parser(path: Path, *, extract: bool, timeout: int = 45) -> dict:
    parser_version()
    try:
        result = subprocess.run([sys.executable, "-m", "research_review_agent.documents.pdf_worker", str(path), "extract" if extract else "inspect"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise DocumentError("PARSER_TIMEOUT", "PDF processing exceeded its time budget; use manual inspection.") from None
    if result.returncode:
        raise DocumentError("PARSER_FAILED", "PDF worker failed or exceeded resources; no substitute text was generated.")
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise DocumentError("PARSER_FAILED", "Parser returned invalid output.") from None
    if "error" in data:
        raise DocumentError(data["error"], data["message"])
    return data


def checksum(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()
