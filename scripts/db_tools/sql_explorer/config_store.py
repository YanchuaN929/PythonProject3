"""Local configuration and output directory utilities."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "sql_explorer"
CONFIG_FILE_NAME = "connection_profile.json"


@dataclass
class ConnectionProfile:
    """Connection profile persisted on local machine."""

    host: str = ""
    port: int = 1433
    database: str = "master"
    username: str = ""
    password: str = ""
    driver_preference: str = "auto"  # auto/pymssql/pyodbc
    encrypt: bool = False
    trust_server_certificate: bool = True


def get_user_config_dir() -> Path:
    """Get per-user config directory."""

    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home()
    config_dir = base / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_profile_path() -> Path:
    """Get local persisted profile path."""

    return get_user_config_dir() / CONFIG_FILE_NAME


def load_profile() -> Optional[ConnectionProfile]:
    """Load saved connection profile if exists."""

    profile_path = get_profile_path()
    if not profile_path.exists():
        return None

    try:
        content = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return ConnectionProfile(
        host=str(content.get("host", "")).strip(),
        port=int(content.get("port", 1433)),
        database=str(content.get("database", "master")).strip() or "master",
        username=str(content.get("username", "")).strip(),
        password=str(content.get("password", "")),
        driver_preference=str(content.get("driver_preference", "auto")).strip().lower()
        or "auto",
        encrypt=bool(content.get("encrypt", False)),
        trust_server_certificate=bool(content.get("trust_server_certificate", True)),
    )


def save_profile(profile: ConnectionProfile) -> Path:
    """Persist connection profile locally."""

    profile_path = get_profile_path()
    data = asdict(profile)
    profile_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profile_path


def clear_profile() -> None:
    """Delete local profile if present."""

    profile_path = get_profile_path()
    if profile_path.exists():
        profile_path.unlink()


def merge_profile(
    base: Optional[ConnectionProfile], overrides: Dict[str, Any]
) -> ConnectionProfile:
    """Merge profile with CLI overrides."""

    profile = base or ConnectionProfile()
    for key, value in overrides.items():
        if value is None:
            continue
        if not hasattr(profile, key):
            continue
        setattr(profile, key, value)
    return profile


def ensure_output_root(output_root: Optional[str]) -> Path:
    """Ensure output root directory."""

    if output_root:
        root = Path(output_root)
    else:
        root = Path.cwd() / "sql_explorer_output"
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_run_output_dir(output_root: Optional[str]) -> Path:
    """Create timestamped output folder for current run."""

    root = ensure_output_root(output_root)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
