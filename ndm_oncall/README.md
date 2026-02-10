# NDM On-Call (Local + Desktop)

This repo provides a local-only workflow that detects incoming Google Voice calls in Chrome, normalizes phone numbers, performs Gmail read-only searches, and shows a lightweight workspace UI with notes, call history, and Gmail results. It also includes a lightweight Windows desktop wrapper (Tauri) that auto-starts the backend and opens the UI without running `uvicorn` manually.

This README is the single source of truth for setup, build, and troubleshooting.

## High-level architecture

- Chrome Extension (MV3)
  - Content script runs on https://voice.google.com/*
  - Detects caller number using fast DOM anchors
  - Sends payload to the local FastAPI backend via a background service worker
- Local FastAPI backend
  - Receives incoming-call payloads
  - Stores call events in SQLite
  - Runs Gmail search (read-only) and caches email links
  - Provides SSE updates for the UI
- Local UI
  - Displays caller info, filtered call history, notes, and Gmail results
  - Consumes SSE for real-time updates
- Desktop wrapper (Tauri)
  - Starts the backend as a sidecar process
  - Waits for /health, then loads http://127.0.0.1:8787/ui

## Folder structure (workspace)

Exp_2/

- chrome_extension/
  - manifest.json
  - background.js
  - content.js
- ndm_oncall/
  - README.md
  - main.py
  - db.py
  - gmail_client.py
  - recording.py
  - app_paths.py
  - ndm_backend.py
  - requirements.txt
  - static/
    - ui.css
    - ui.js
    - favicon.ico
  - templates/
    - ui.html
- ndm_desktop/
  - dist/
  - assets/
  - src-tauri/
  - scripts/
- .venv/

Notes:

- credentials.json and token.json contain Gmail OAuth secrets/tokens (local only).
- data.db lives in %APPDATA%\NDM\data.db (app data directory).
- recordings are stored in %APPDATA%\NDM\recordings\

## End-to-end data flow

1. Chrome extension detects the phone number from the call UI.
2. Extension sends payload to POST /incoming_call.
3. Backend stores call, emits SSE event, and runs Gmail search in background.
4. UI updates immediately via SSE and then updates emails when Gmail results are ready.
5. UI fetches /call_history?digits=... and shows only the last 3 matching calls.

## Chrome extension details

Location: chrome_extension/

Detection strategy (ultrafast)

- Triggered only when call UI nodes are inserted or updated
- Runs every 50ms for up to 2 seconds
- Stops immediately when a valid number is found
- Do not resend identical digits within 15s
- Short pause after send (3s) to avoid duplicate bursts

Validation and normalization

- 10 digits
- OR 11 digits starting with 1

## Backend (FastAPI) details

Location: ndm_oncall/

Core endpoints

- POST /incoming_call
  - Body: { raw, digits, last10, variants }
  - Stores call event in SQLite
  - Emits SSE event "incoming_call_workspace"
  - Starts async Gmail search and emits "gmail_results_ready"
- GET /call_history
  - Query: digits=... OR last10=...
  - Returns only matching calls
  - Limit: 3
  - If no digits/last10, returns empty list
- GET /workspace/{phone_digits}
  - Returns caller workspace payload
- GET /events
  - Server-sent events stream
- GET /health
  - Health check
- POST /notes
  - Body: { call_id, note_text }
  - Appends note to call
- POST /reset_db
  - Clears all local data from SQLite

Time handling

- Timestamps are stored in local machine time (datetime.now().isoformat()).
- UI formats timestamps in Central Time (America/Chicago).
- If the OS lacks IANA timezone data, server still stores local time without timezone conversion.

## Gmail search behavior

- Read-only Gmail API
- OR query across number variants
- Results cached in SQLite (email_links table)

OAuth files

- Place credentials.json in %APPDATA%\NDM\ (preferred) or ndm_oncall/
- token.json is created after the first OAuth login in %APPDATA%\NDM\

## Recording status

- Recording code exists but is currently disabled in the UI and backend.

## Local dev setup (backend + web UI)

Prerequisites

- Windows 10/11
- Python 3.10+
- Google Chrome

Install dependencies

- python -m venv .venv
- .venv\Scripts\activate
- pip install -r ndm_oncall\requirements.txt

Run the backend

- python -m uvicorn ndm_oncall.main:app --host 127.0.0.1 --port 8787

Open the UI

- http://127.0.0.1:8787/ui

Chrome extension setup

1. Chrome -> Extensions -> Enable Developer mode
2. Load unpacked
3. Select chrome_extension/
4. Open https://voice.google.com/

## NDM Desktop (Tauri)

Lightweight desktop wrapper that auto-starts the backend and opens the existing UI at http://127.0.0.1:8787/ui.

Dev mode (fast iteration)

1. Start the backend (keep port 8787):

- python -m uvicorn ndm_oncall.main:app --host 127.0.0.1 --port 8787

2. Run the desktop shell (from repo root):

- cd ndm_desktop
- npm install
- set NDM_SKIP_SIDECAR=1
- npm run dev

Build release (no Python install needed on target machines)

1. Build the backend sidecar (from repo root):

- pip install pyinstaller
- .\ndm_desktop\scripts\build_backend.ps1

2. Build the Tauri app:

- cd ndm_desktop
- npm install
- npm run build

Build outputs

- Installer (NSIS): ndm_desktop\src-tauri\target\release\bundle\nsis\NDM_0.1.0_x64-setup.exe
- Installer (MSI): ndm_desktop\src-tauri\target\release\bundle\msi\NDM_0.1.0_x64_en-US.msi
- Raw exe: ndm_desktop\src-tauri\target\release\NDM.exe

App data locations (Windows)

- SQLite: %APPDATA%\NDM\data.db
- OAuth: %APPDATA%\NDM\credentials.json and token.json
- Recordings: %APPDATA%\NDM\recordings\
- Backend logs: %APPDATA%\NDM\ndm_backend.log
- Desktop logs: %APPDATA%\NDM\ndm_desktop.log

## Testing checklist

1. Start backend and open UI:

- http://127.0.0.1:8787/ui

2. In Chrome DevTools (voice.google.com) confirm content script logs:

- content script boot
- BURST_START
- CALL_FOUND
- POST_OK

3. Backend logs:

- INCOMING_CALL
- GMAIL_QUERY

4. UI updates:

- Caller info updates
- Recent calls shows only 3 items for that number
- Gmail results appear after the search completes

## Resetting local data

Call the reset endpoint:

- PowerShell:
  Invoke-RestMethod -Uri http://127.0.0.1:8787/reset_db -Method Post
- curl:
  curl -X POST http://127.0.0.1:8787/reset_db

## Troubleshooting

- Desktop shows "Backend failed to start":
  - Check %APPDATA%\NDM\ndm_backend.log
  - Check %APPDATA%\NDM\ndm_desktop.log
- If Gmail auth is missing, place credentials.json in %APPDATA%\NDM\ (preferred) or ndm_oncall/
- token.json is created after the first OAuth login
- If call detection seems late, confirm the content script is injected in the correct frame
- UI always filters history per current digits; it never shows all calls
- If timestamps look incorrect, reset DB and ensure UI uses Central Time formatting

## Files of interest

- chrome_extension/content.js
- chrome_extension/background.js
- chrome_extension/manifest.json
- ndm_oncall/main.py
- ndm_oncall/db.py
- ndm_oncall/static/ui.js
- ndm_oncall/static/ui.css
- ndm_oncall/templates/ui.html
- ndm_desktop/src-tauri/src/main.rs
