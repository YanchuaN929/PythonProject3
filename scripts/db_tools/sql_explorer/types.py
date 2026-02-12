"""Shared type declarations for SQL explorer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RunMetadata:
    """Runtime metadata snapshot."""

    host: str
    database: str
    connector: str
    table_limit: int
    sample_top_n: int


@dataclass
class CandidateGroup:
    """Candidate group for one semantic target."""

    category: str
    rows: List[Dict[str, Any]] = field(default_factory=list)
