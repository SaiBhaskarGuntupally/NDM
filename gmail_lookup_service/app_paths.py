from __future__ import annotations

import sys
from pathlib import Path

from shared.app_paths import get_app_data_dir, get_db_path


def get_resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    else:
        base = Path(__file__).parent
    return base


def get_recordings_dir() -> Path:
    recordings_dir = get_app_data_dir() / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return recordings_dir


def get_credentials_path() -> Path:
    app_credentials = get_app_data_dir() / "credentials.json"
    if app_credentials.exists():
        return app_credentials
    return Path(__file__).parent / "credentials.json"


def get_token_path() -> Path:
    return get_app_data_dir() / "token.json"


def get_log_path() -> Path:
    return get_app_data_dir() / "ndm_backend.log"
