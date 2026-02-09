from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import sqlite3
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from shared import profile_store
from fastapi.templating import Jinja2Templates

from ndm_research import db
from shared.app_paths import get_db_path
from shared.sqlite_utils import get_journal_mode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ndm_research")

app = FastAPI(title="NDM Research")

RESOURCE_DIR = Path(__file__).parent
TEMPLATES_DIR = RESOURCE_DIR / "templates"
STATIC_DIR = RESOURCE_DIR / "static"
SHARED_STATIC_DIR = RESOURCE_DIR.parent / "shared" / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_query(value: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    digits = normalize_digits(value)
    if not digits:
        return None, None, None
    if len(digits) == 11 and digits.startswith("1"):
        last10 = digits[1:]
        return last10, last10[-4:], None
    if len(digits) >= 10:
        last10 = digits[-10:]
        return last10, last10[-4:], None
    if len(digits) == 4:
        return None, digits, None
    return None, None, digits


def normalize_last10(value: str) -> str:
    digits = normalize_digits(value)
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def format_phone(last10: str) -> str:
    if not last10:
        return ""
    cleaned = normalize_digits(last10)
    if len(cleaned) == 10:
        return f"+1-{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:]}"
    return cleaned


def get_db_conn():
    conn = db.get_db()
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    db_path = get_db_path()
    logger.info("NDM_RESEARCH_DB_PATH=%s", db_path)
    conn = db.get_db()
    try:
        journal_mode = get_journal_mode(conn)
    finally:
        conn.close()
    logger.info("DB_JOURNAL_MODE %s", journal_mode)


@app.get("/research", response_class=HTMLResponse)
def research_home(request: Request):
    return templates.TemplateResponse(
        "research.html",
        {"request": request},
    )

@app.get("/research/profile-data/{digits}")
def research_profile_data(digits: str):
    profile = profile_store.load_profile(digits)
    return {"ok": True, "profile": profile}


@app.put("/research/profile-data/{digits}")
async def research_profile_update(digits: str, request: Request):
    payload = await request.json()
    payload["phone_digits"] = digits
    profile = profile_store.save_profile(payload)
    return {"ok": True, "profile": profile}


@app.post("/research/profile-data/{digits}/notes")
async def research_profile_note(digits: str, request: Request):
    payload = await request.json()
    notes = profile_store.add_note(digits, payload.get("note_text", ""))
    return {"ok": True, "notes": notes}


@app.get("/research/search")
def research_search(
    q: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db_conn)
):
    query = (q or "").strip()
    if not query:
        return {"ok": True, "results": []}

    last10, last4, partial = normalize_query(query)
    results: Dict[str, Dict[str, Any]] = {}

    if last10:
        for row in db.search_calls_by_last10(conn, last10, limit=100):
            results[row["phone_digits"]] = row
        for row in db.search_profiles_by_last10(conn, last10, limit=100):
            results.setdefault(row["phone_digits"], {}).update(row)
    elif last4:
        for row in db.search_calls_by_last4(conn, last4, limit=120):
            results[row["phone_digits"]] = row
        for row in db.search_profiles_by_last4(conn, last4, limit=120):
            results.setdefault(row["phone_digits"], {}).update(row)
    elif partial:
        for row in db.search_calls_by_partial(conn, partial, limit=120):
            results[row["phone_digits"]] = row
        for row in db.search_profiles_by_partial(conn, partial, limit=120):
            results.setdefault(row["phone_digits"], {}).update(row)

    formatted_results = []
    for phone_digits, row in results.items():
        formatted_results.append(
            {
                "phone_digits": phone_digits,
                "formatted": format_phone(phone_digits),
                "vendor_name": row.get("vendor_name"),
                "last_call_ts": row.get("last_call_ts"),
                "call_count": row.get("call_count", 0),
                "display_name": row.get("display_name"),
            }
        )
    formatted_results.sort(
        key=lambda item: item.get("last_call_ts") or "", reverse=True
    )
    return {"ok": True, "results": formatted_results}


@app.get("/research/numbers")
def research_numbers(
    limit: int = 500,
    offset: int = 0,
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    limit = max(1, min(limit, 2000))
    offset = max(0, offset)
    rows = db.list_all_numbers(conn, limit=limit, offset=offset)
    results = []
    for row in rows:
        results.append(
            {
                "phone_digits": row.get("phone_digits"),
                "formatted": format_phone(row.get("phone_digits")),
                "vendor_name": row.get("vendor_name"),
                "last_call_ts": row.get("last_call_ts"),
                "call_count": row.get("call_count", 0),
                "display_name": row.get("display_name"),
            }
        )
    return {"ok": True, "results": results}


def build_workspace_data(
    conn: sqlite3.Connection,
    phone_digits: str,
    offset: int,
    limit: int,
) -> Dict[str, Any]:
    normalized = normalize_last10(phone_digits)

    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    profile = db.get_profile(conn, normalized) if normalized else None
    calls = db.list_calls(conn, normalized, limit + 1, offset) if normalized else []
    has_more_calls = len(calls) > limit
    calls = calls[:limit]
    call_notes = db.list_call_notes(conn, normalized, limit=200) if normalized else []
    research_notes = (
        db.list_research_notes(conn, normalized, limit=200) if normalized else []
    )
    notes: list[dict] = []
    for item in call_notes:
        notes.append(
            {
                "id": item["id"],
                "note_text": item["note_text"],
                "ts": item["ts"],
                "source": "call",
                "call_id": item.get("call_id"),
            }
        )
    for item in research_notes:
        notes.append(
            {
                "id": item["id"],
                "note_text": item["note_text"],
                "ts": item["ts"],
                "source": "research",
                "call_id": None,
            }
        )
    notes.sort(key=lambda item: item.get("ts") or "", reverse=True)

    emails = db.list_email_links(conn, normalized) if normalized else []
    recordings = db.list_recordings(conn, normalized) if normalized else []
    latest_call_id = db.get_latest_call_id(conn, normalized) if normalized else None
    stats = db.get_call_stats(conn, normalized) if normalized else {}
    display_name = (
        db.get_latest_call_display_name(conn, normalized) if normalized else None
    )
    jd_text = db.get_jd_text(conn, normalized) if normalized else ""
    resume_text = db.get_resume_text(conn, normalized) if normalized else ""

    return {
        "phone_digits": normalized,
        "formatted": format_phone(normalized),
        "profile": profile,
        "display_name": display_name,
        "calls": calls,
        "notes": notes,
        "emails": emails,
        "recordings": recordings,
        "jd_text": jd_text,
        "resume_text": resume_text,
        "latest_call_id": latest_call_id,
        "call_count": stats.get("call_count", 0),
        "last_call_ts": stats.get("last_call_ts"),
        "has_more_calls": has_more_calls,
        "offset": offset,
        "limit": limit,
        "has_profile": bool(profile),
    }


@app.get("/research/workspace/{digits}", response_class=HTMLResponse)
def research_workspace(
    request: Request,
    digits: str,
    offset: int = 0,
    limit: int = 100,
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    workspace = build_workspace_data(conn, digits, offset=offset, limit=limit)
    return templates.TemplateResponse(
        "workspace.html",
        {"request": request, "workspace": workspace},
    )


@app.get("/research/workspace/{digits}/data")
def research_workspace_data(
    digits: str,
    offset: int = 0,
    limit: int = 100,
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    data = build_workspace_data(conn, digits, offset=offset, limit=limit)
    return JSONResponse(content={"ok": True, "workspace": data})


@app.post("/research/profile")
async def create_profile(
    request: Request, conn: sqlite3.Connection = Depends(get_db_conn)
):
    payload = await request.json()
    last10, last4, _ = normalize_query(payload.get("phone_digits", ""))
    if not last10 or not last4:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "phone_digits required"}
        )
    db.upsert_profile(
        conn,
        last10,
        last4,
        payload.get("vendor_name"),
        payload.get("vendor_company"),
        payload.get("vendor_title"),
    )
    db.ensure_jd(conn, last10)
    db.ensure_resume(conn, last10)
    return {"ok": True, "phone_digits": last10}


@app.put("/research/profile/{phone_digits}")
async def update_profile(
    phone_digits: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)
):
    payload = await request.json()
    last10, last4, _ = normalize_query(phone_digits)
    if not last10 or not last4:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "phone_digits required"}
        )
    db.upsert_profile(
        conn,
        last10,
        last4,
        payload.get("vendor_name"),
        payload.get("vendor_company"),
        payload.get("vendor_title"),
    )
    return {"ok": True}


@app.put("/research/jd/{phone_digits}")
async def update_jd(
    phone_digits: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)
):
    payload = await request.json()
    last10, _, _ = normalize_query(phone_digits)
    if not last10:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "phone_digits required"}
        )
    db.upsert_jd(conn, last10, payload.get("jd_text", ""))
    return {"ok": True}


@app.put("/research/resume/{phone_digits}")
async def update_resume(
    phone_digits: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)
):
    payload = await request.json()
    last10, _, _ = normalize_query(phone_digits)
    if not last10:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "phone_digits required"}
        )
    db.upsert_resume(conn, last10, payload.get("resume_text", ""))
    return {"ok": True}


@app.post("/research/note")
async def create_note(
    request: Request, conn: sqlite3.Connection = Depends(get_db_conn)
):
    payload = await request.json()
    call_id = payload.get("call_id")
    note_text = (payload.get("note_text") or "").strip()
    last10, last4, _ = normalize_query(payload.get("phone_digits", ""))
    if not note_text:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "note_text required"},
        )

    if call_id:
        note = db.add_call_note(conn, int(call_id), note_text)
        return {"ok": True, "note": note}

    if not last10 or not last4:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "phone_digits required"},
        )
    note = db.add_research_note(conn, last10, note_text)
    return {"ok": True, "note": note}


@app.put("/research/note/{note_id}")
async def update_note(
    note_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)
):
    payload = await request.json()
    note_text = (payload.get("note_text") or "").strip()
    if not note_text:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "note_text required"}
        )
    updated = db.update_note_any(conn, note_id, note_text)
    if not updated:
        return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
    return {"ok": True}


@app.delete("/research/note/{note_id}")
def delete_note(note_id: int, conn: sqlite3.Connection = Depends(get_db_conn)):
    deleted = db.delete_note_any(conn, note_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
    return {"ok": True}


@app.delete("/research/call/{call_id}")
def delete_call(call_id: int, conn: sqlite3.Connection = Depends(get_db_conn)):
    db.delete_call(conn, call_id)
    return {"ok": True}


app.mount("/research/static", StaticFiles(directory=str(STATIC_DIR)), name="research_static")
if SHARED_STATIC_DIR.exists():
    app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared-static")
