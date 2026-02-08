from __future__ import annotations

import os
import traceback

import uvicorn

from gmail_lookup_service import app_paths


def main() -> None:
    try:
        from gmail_lookup_service.main import app

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8787,
            log_level=os.environ.get("NDM_LOG_LEVEL", "info"),
            reload=False,
        )
    except Exception:  # noqa: BLE001
        log_path = app_paths.get_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("NDM backend failed to start.\n")
            log_file.write(traceback.format_exc())
            log_file.write("\n")


if __name__ == "__main__":
    main()
