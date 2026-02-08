from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "NDM"


def get_app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        base_dir = Path(base)
    else:
        base_dir = Path.home() / "AppData" / "Roaming"
    app_dir = base_dir / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_db_path() -> Path:
    return get_app_data_dir() / "data.db"
