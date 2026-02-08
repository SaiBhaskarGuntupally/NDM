# NDM Research

NDM Research is a lightweight FastAPI app that reads and writes the same SQLite database as NDM OnCall. It runs on port 8788 and is designed for search/edit/delete workflows.

## Run

- OnCall (existing):
  - `uvicorn gmail_lookup_service.main:app --reload --port 8787`
- Research:
  - `uvicorn ndm_research.main:app --reload --port 8788`

Both apps log the resolved DB path at startup. They must match.

## Notes

- The DB path is shared via `shared/app_paths.py` and points to `%APPDATA%\NDM\data.db`.
- SQLite is configured for WAL, `synchronous=NORMAL`, and an 8s busy timeout in Research.
- Writes are committed immediately after each change.
