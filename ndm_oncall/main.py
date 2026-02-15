from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ndm_oncall import app_paths, db
from shared import profile_store
from ndm_oncall.gmail_client import search_messages, get_mailbox_context
from ndm_oncall.recording import RecordingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(app_paths.get_log_path(), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ndm_oncall")

app = FastAPI(title="NDM OnCall")

RESOURCE_DIR = app_paths.get_resource_dir()
TEMPLATES_DIR = RESOURCE_DIR / "templates"
STATIC_DIR = RESOURCE_DIR / "static"
SHARED_STATIC_DIR = RESOURCE_DIR.parent / "shared" / "static"
RECORDINGS_DIR = app_paths.get_recordings_dir()

LATEST_RESULTS: List[dict] = []
LATEST_NUMBER: Optional[str] = None
EVENT_QUEUES: List[asyncio.Queue] = []
RECORDING_MANAGER = RecordingManager(RECORDINGS_DIR)
ACTIVE_CALL_ID: Optional[int] = None
ACTIVE_PHONE_DIGITS: Optional[str] = None

db.init_db()
logger.info("DB_PATH %s", app_paths.get_db_path())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://voice.google.com"],
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_private_network_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


class IncomingCall(BaseModel):
    raw: str
    digits: str
    last10: str
    variants: List[str]


@app.post("/incoming_call")
async def incoming_call(payload: IncomingCall, request: Request):
    t0 = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    logger.info("INCOMING_CALL payload=%s client_ip=%s", payload.model_dump(), client_ip)

    if not payload.digits:
        logger.info("INCOMING_CALL digits=empty")
        return {"ok": True, "results": []}

    variants = payload.variants or []
    quoted = [f'"{v}"' for v in variants if v]
    query = " OR ".join(quoted)
    query = f"in:inbox ({query})" if query else "in:inbox"

    logger.info("INCOMING_CALL digits=%s", payload.digits)
    logger.info("GMAIL_QUERY %s", query)

    global ACTIVE_CALL_ID, ACTIVE_PHONE_DIGITS
    if (
        RECORDING_MANAGER.active
        and payload.digits == ACTIVE_PHONE_DIGITS
        and RECORDING_MANAGER.active_call_id
    ):
        active_call_id = int(RECORDING_MANAGER.active_call_id)
        ACTIVE_CALL_ID = active_call_id
        recent_calls = _sanitize_calls(db.list_recent_calls(limit=20))
        opportunity = db.get_opportunity(payload.digits)
        emails_cached = _apply_mailbox_context(db.list_email_links(payload.digits))
        emit_event(
            "incoming_call_workspace",
            {
                "phone_digits": payload.digits,
                "call_id": active_call_id,
                "display_name": None,
                "recent_calls": recent_calls,
                "notes": [],
                "opportunity": opportunity,
                "emails": emails_cached,
                "recording_active": _recording_active_for_call(active_call_id),
            },
        )
        return {"ok": True, "results": []}

    call_id = db.create_call(payload.digits, status="incoming")
    recent_calls = _sanitize_calls(db.list_recent_calls(limit=20))
    opportunity = db.get_opportunity(payload.digits)
    emails_cached = _apply_mailbox_context(db.list_email_links(payload.digits))

    t1 = time.perf_counter()
    emit_event(
        "incoming_call_workspace",
        {
            "phone_digits": payload.digits,
            "call_id": call_id,
            "display_name": None,
            "recent_calls": recent_calls,
            "notes": [],
            "opportunity": opportunity,
            "emails": emails_cached,
            "recording_active": _recording_active_for_call(call_id),
        },
    )
    t2 = time.perf_counter()

    # rec_result = RECORDING_MANAGER.start(payload.digits)
    # if rec_result.ok:
    #     ACTIVE_CALL_ID = call_id
    #     ACTIVE_PHONE_DIGITS = payload.digits
    #     emit_event(
    #         "recording_started",
    #         {
    #             "phone_digits": payload.digits,
    #             "call_id": call_id,
    #             "mic_path": rec_result.mic_path,
    #             "sys_path": rec_result.sys_path,
    #         },
    #     )
    # else:
    #     emit_event(
    #         "recording_stopped",
    #         {"phone_digits": payload.digits, "call_id": call_id, "error": rec_result.error},
    #     )
    t3 = time.perf_counter()

    async def gmail_task():
        t4 = time.perf_counter()
        try:
            results = await asyncio.to_thread(search_messages, query, 5)
        except FileNotFoundError as exc:
            logger.error("GMAIL_AUTH_MISSING %s", exc)
            results = []
        except Exception as exc:  # noqa: BLE001
            logger.exception("GMAIL_SEARCH_ERROR %s", exc)
            results = []

        db.save_email_links(
            payload.digits,
            results,
            opportunity_id=opportunity["id"] if opportunity else None,
        )
        global LATEST_RESULTS, LATEST_NUMBER
        LATEST_RESULTS = results
        LATEST_NUMBER = payload.digits
        emit_event(
            "gmail_results_ready",
            {"phone_digits": payload.digits, "emails": _apply_mailbox_context(results)},
        )
        t5 = time.perf_counter()
        logger.info(
            "LATENCY t0->t1=%.0fms t1->t2=%.0fms t4->t5=%.0fms",
            (t1 - t0) * 1000,
            (t2 - t1) * 1000,
            (t5 - t4) * 1000,
        )

    asyncio.create_task(gmail_task())
    logger.info(
        "LATENCY t0->emit=%.0fms t2->rec=%.0fms",
        (t2 - t0) * 1000,
        (t3 - t2) * 1000,
    )
    return {"ok": True, "results": []}


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/latest")
def latest():
    return {"ok": True, "number": LATEST_NUMBER, "results": LATEST_RESULTS}


@app.post("/clear")
def clear():
    global LATEST_RESULTS, LATEST_NUMBER
    LATEST_RESULTS = []
    LATEST_NUMBER = None
    return {"ok": True}


@app.get("/call_history")
def call_history(digits: Optional[str] = None, last10: Optional[str] = None):
    if not digits and not last10:
        return {"ok": True, "calls": []}
    calls = _sanitize_calls(db.list_call_history(digits=digits, last10=last10, limit=3))
    return {"ok": True, "calls": calls}


@app.post("/reset_db")
def reset_db():
    db.clear_all()
    return {"ok": True}


@app.get("/ui", response_class=HTMLResponse)
def ui():
    html = (TEMPLATES_DIR / "ui.html").read_text(encoding="utf-8")
    # Inject profile.js inline to avoid browser caching issues
    profile_js = ""
    profile_js_path = SHARED_STATIC_DIR / "profile.js"
    if profile_js_path.exists():
        profile_js = profile_js_path.read_text(encoding="utf-8")
    html = html.replace("<!-- INJECT_PROFILE_JS -->", f"<script>\n{profile_js}\n</script>")
    return HTMLResponse(content=html)


@app.get("/machaa-mode/portrait", response_class=HTMLResponse)
def machaa_mode_portrait():
    html = (TEMPLATES_DIR / "machaa_mode_portrait.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/profile-data/{digits}")
def profile_data(digits: str):
    profile = profile_store.load_profile(digits)
    return {"ok": True, "profile": profile}


@app.put("/profile-data/{digits}")
async def profile_data_update(digits: str, request: Request):
    payload = await request.json()
    payload["phone_digits"] = digits
    profile = profile_store.save_profile(payload)
    return {"ok": True, "profile": profile}


@app.post("/profile-data/{digits}/notes")
async def profile_note(digits: str, request: Request):
    payload = await request.json()
    notes = profile_store.add_note(digits, payload.get("note_text", ""))
    return {"ok": True, "notes": notes}


@app.get("/favicon.ico")
def favicon():
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return HTMLResponse(status_code=404, content="")


@app.get("/events")
async def events():
    queue: asyncio.Queue = asyncio.Queue()
    EVENT_QUEUES.append(queue)

    async def event_generator():
        try:
            while True:
                event_type, data = await queue.get()
                payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                yield payload
        finally:
            EVENT_QUEUES.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def emit_event(event_type: str, data: dict) -> None:
    for q in EVENT_QUEUES:
        q.put_nowait((event_type, data))


def _audio_path_if_valid(audio_path: Optional[str]) -> Optional[str]:
    if not audio_path:
        return None
    try:
        normalized = str(audio_path).replace("\\", "/")
        prefix = "/recordings/"
        if not normalized.startswith(prefix):
            return None
        rel = normalized[len(prefix):].strip("/")
        if not rel:
            return None
        file_path = (RECORDINGS_DIR / rel).resolve()
        base_dir = RECORDINGS_DIR.resolve()
        try:
            file_path.relative_to(base_dir)
        except ValueError:
            return None
        if not file_path.exists():
            return None
        if file_path.stat().st_size <= 1024:
            return None
        rel_norm = rel.replace("\\", "/")
        return f"/recordings/{rel_norm}"
    except Exception:  # noqa: BLE001
        return None


def _sanitize_calls(calls: List[dict]) -> List[dict]:
    for call in calls:
        call["audio_path"] = _audio_path_if_valid(call.get("audio_path"))
    return calls


def _apply_mailbox_context(emails: List[dict]) -> List[dict]:
    if not emails:
        return emails
    try:
        mailbox_email, account_index = get_mailbox_context()
    except Exception:  # noqa: BLE001
        return emails
    for email in emails:
        if mailbox_email and not email.get("mailbox_email"):
            email["mailbox_email"] = mailbox_email
        if account_index and not email.get("account_index"):
            email["account_index"] = account_index
    return emails


def _recording_active_for_call(call_id: Optional[int]) -> bool:
    if not call_id:
        return False
    return RECORDING_MANAGER.is_active_for_call(int(call_id))


def _public_audio_path_for_call(call_id: int, path_value: Optional[str]) -> Optional[str]:
    if not path_value:
        return None
    try:
        path_obj = Path(path_value)
        if not path_obj.exists():
            return None
        expected_dir = (RECORDINGS_DIR / str(call_id)).resolve()
        resolved = path_obj.resolve()
        try:
            resolved.relative_to(expected_dir)
        except ValueError:
            return None
        if path_obj.name not in {"mic.wav", "system.wav"}:
            return None
        return f"/recordings/{call_id}/{path_obj.name}"
    except Exception:  # noqa: BLE001
        return None


def _recording_response(
    *,
    ok: bool,
    call_id: int,
    recording_active: bool,
    audio_paths: Optional[dict] = None,
    reason: Optional[str] = None,
) -> dict:
    response = {
        "ok": bool(ok),
        "call_id": str(call_id),
        "recording_active": bool(recording_active),
    }
    if audio_paths:
        response["audio_paths"] = audio_paths
    if reason:
        response["reason"] = reason
    return response


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/notes")
def add_note(payload: dict):
    call_id = payload.get("call_id")
    note_text = payload.get("note_text", "")
    if not call_id or not note_text:
        return {"ok": False, "error": "call_id and note_text required"}
    db.add_note(int(call_id), note_text)
    notes = db.get_notes(int(call_id))
    return {"ok": True, "notes": notes}


@app.post("/recording/start")
def start_recording(call_id: int):
    call = db.get_call_by_id(int(call_id))
    if not call:
        return _recording_response(
            ok=False,
            call_id=int(call_id),
            recording_active=_recording_active_for_call(int(call_id)),
            reason="call_not_found",
        )

    global ACTIVE_CALL_ID, ACTIVE_PHONE_DIGITS
    rec_result = RECORDING_MANAGER.start(
        call_id=int(call_id),
        phone_digits=call.get("phone_digits", ""),
    )
    if not rec_result.ok:
        return _recording_response(
            ok=False,
            call_id=int(call_id),
            recording_active=_recording_active_for_call(int(call_id)),
            reason=rec_result.reason,
        )

    ACTIVE_CALL_ID = int(call_id)
    ACTIVE_PHONE_DIGITS = call.get("phone_digits")
    audio_paths = {}
    mic_public = _public_audio_path_for_call(int(call_id), rec_result.mic_path)
    sys_public = _public_audio_path_for_call(int(call_id), rec_result.sys_path)
    if mic_public:
        audio_paths["mic_path"] = mic_public
    if sys_public:
        audio_paths["sys_path"] = sys_public
    emit_event(
        "recording_started",
        {
            "call_id": int(call_id),
            "recording_active": _recording_active_for_call(int(call_id)),
            "audio_paths": audio_paths,
        },
    )
    return _recording_response(
        ok=True,
        call_id=int(call_id),
        recording_active=_recording_active_for_call(int(call_id)),
        audio_paths=audio_paths or None,
    )


@app.post("/recording/stop")
def stop_recording(call_id: int):
    global ACTIVE_CALL_ID, ACTIVE_PHONE_DIGITS
    rec_result = RECORDING_MANAGER.stop(int(call_id))
    if not rec_result.ok:
        return _recording_response(
            ok=False,
            call_id=int(call_id),
            recording_active=_recording_active_for_call(int(call_id)),
            reason=rec_result.reason,
        )

    audio_paths: dict = {}
    mic_public = _public_audio_path_for_call(int(call_id), rec_result.mic_path)
    sys_public = _public_audio_path_for_call(int(call_id), rec_result.sys_path)
    if mic_public:
        audio_paths["mic_path"] = mic_public
    if sys_public:
        audio_paths["sys_path"] = sys_public

    selected_path = audio_paths.get("sys_path") or audio_paths.get("mic_path")
    if selected_path:
        db.update_call_audio(int(call_id), selected_path)
    db.update_call_end(int(call_id))

    call = db.get_call_by_id(int(call_id))
    if call and selected_path:
        db.add_research_recording(
            call_id=int(call_id),
            phone_digits=call.get("phone_digits", ""),
            audio_path=selected_path,
            duration_sec=int(rec_result.duration_sec or 0),
        )

    if ACTIVE_CALL_ID == int(call_id):
        ACTIVE_CALL_ID = None
        ACTIVE_PHONE_DIGITS = None

    recording_active = _recording_active_for_call(int(call_id))
    emit_event(
        "recording_stopped",
        {
            "call_id": int(call_id),
            "recording_active": recording_active,
            "audio_paths": audio_paths,
        },
    )
    return _recording_response(
        ok=True,
        call_id=int(call_id),
        recording_active=recording_active,
        audio_paths=audio_paths or None,
    )


@app.get("/recording/status")
def recording_status(call_id: int):
    status = RECORDING_MANAGER.status(int(call_id))
    recording_active = bool(status.get("recording_active"))
    response = _recording_response(
        ok=True,
        call_id=int(call_id),
        recording_active=recording_active,
        reason=status.get("reason"),
    )
    raw_paths = status.get("audio_paths") or {}
    mic_public = _public_audio_path_for_call(int(call_id), raw_paths.get("mic_path"))
    sys_public = _public_audio_path_for_call(int(call_id), raw_paths.get("sys_path"))
    if mic_public or sys_public:
        response["audio_paths"] = {}
        if mic_public:
            response["audio_paths"]["mic_path"] = mic_public
        if sys_public:
            response["audio_paths"]["sys_path"] = sys_public
    return response


@app.get("/workspace/{phone_digits}")
def workspace(phone_digits: str):
    recent_calls = _sanitize_calls(db.list_recent_calls(limit=20))
    opportunity = db.get_opportunity(phone_digits)
    emails = _apply_mailbox_context(db.list_email_links(phone_digits))
    latest_call = db.get_latest_call(phone_digits)
    notes = db.get_notes(latest_call["id"]) if latest_call else []
    current_call_id = latest_call["id"] if latest_call else None
    return {
        "phone_digits": phone_digits,
        "display_name": None,
        "recent_calls": recent_calls,
        "notes": notes,
        "opportunity": opportunity,
        "emails": emails,
        "current_call_id": current_call_id,
        "recording_active": _recording_active_for_call(current_call_id),
    }


@app.post("/opportunity/upsert")
def opportunity_upsert(payload: dict):
    op_id = db.upsert_opportunity(payload)
    return {"ok": True, "id": op_id}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/recordings", StaticFiles(directory=RECORDINGS_DIR), name="recordings")
if SHARED_STATIC_DIR.exists():
    app.mount("/shared", StaticFiles(directory=SHARED_STATIC_DIR), name="shared-static")
