"""Template specification loader."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resource_base() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else _repo_root()


def load_template_spec() -> Dict[str, Any]:
    """Load example/template_spec.json if available."""

    candidate = _resource_base() / "example" / "template_spec.json"
    if not candidate.exists():
        return {}
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return {}
