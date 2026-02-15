from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import sounddevice as sd
import soundfile as sf

logger = logging.getLogger("ndm_oncall")


@dataclass
class RecordingResult:
    ok: bool
    call_id: Optional[int] = None
    mic_path: Optional[str] = None
    sys_path: Optional[str] = None
    reason: Optional[str] = None
    duration_sec: Optional[int] = None


class _StreamWriter:
    def __init__(self, file_path: Path, device: int, samplerate: int, channels: int, loopback: bool = False):
        self.file_path = file_path
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.loopback = loopback
        self.stream = None
        self.file = None

    def start(self) -> None:
        self.file = sf.SoundFile(self.file_path, mode="w", samplerate=self.samplerate, channels=self.channels)
        extra = None
        if self.loopback:
            try:
                extra = sd.WasapiSettings(loopback=True)
            except TypeError:
                try:
                    extra = sd.WasapiSettings()
                    if hasattr(extra, "loopback"):
                        setattr(extra, "loopback", True)
                    else:
                        extra = None
                except Exception:  # noqa: BLE001
                    extra = None
                if extra is None:
                    logger.warning("WASAPI loopback not supported by this sounddevice build; system audio capture may be unavailable.")
            if extra is None:
                raise RuntimeError("wasapi_loopback_unsupported")
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            device=self.device,
            channels=self.channels,
            callback=self._callback,
            extra_settings=extra,
        )
        self.stream.start()

    def _callback(self, indata, frames, time, status):  # noqa: ARG002
        if status:
            logger.warning("Recording status: %s", status)
        if self.file:
            self.file.write(indata)

    def stop(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if self.file:
            self.file.close()


class RecordingManager:
    def __init__(self, recordings_dir: Path):
        self.recordings_dir = recordings_dir
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.is_active = False
        self.active_call_id: Optional[int] = None
        self.active_phone_digits: str = ""
        self.started_monotonic: Optional[float] = None
        self.mic_writer: Optional[_StreamWriter] = None
        self.sys_writer: Optional[_StreamWriter] = None
        self.mic_path: Optional[str] = None
        self.sys_path: Optional[str] = None

    @property
    def active(self) -> bool:
        return self.is_active

    def _reset_state(self) -> None:
        self.is_active = False
        self.active_call_id = None
        self.active_phone_digits = ""
        self.started_monotonic = None
        self.mic_writer = None
        self.sys_writer = None
        self.mic_path = None
        self.sys_path = None

    @staticmethod
    def _stop_writer(writer: Optional[_StreamWriter]) -> None:
        if not writer:
            return
        writer.stop()

    @staticmethod
    def _remove_file_if_exists(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except Exception:  # noqa: BLE001
            logger.warning("Unable to remove existing recording file: %s", path)

    def start(self, call_id: int, phone_digits: str = "") -> RecordingResult:
        with self._lock:
            if self.is_active:
                return RecordingResult(ok=False, call_id=call_id, reason="already_active")

            try:
                default_input = sd.default.device[0]
                default_output = sd.default.device[1]
                input_info = sd.query_devices(default_input, "input")
                output_info = sd.query_devices(default_output, "output")

                call_dir = self.recordings_dir / str(call_id)
                call_dir.mkdir(parents=True, exist_ok=True)
                mic_path = call_dir / "mic.wav"
                sys_path = call_dir / "system.wav"
                self._remove_file_if_exists(mic_path)
                self._remove_file_if_exists(sys_path)

                self.mic_writer = _StreamWriter(
                    mic_path,
                    device=default_input,
                    samplerate=int(input_info["default_samplerate"]),
                    channels=min(2, int(input_info["max_input_channels"]) or 1),
                )
                self.sys_writer = _StreamWriter(
                    sys_path,
                    device=default_output,
                    samplerate=int(output_info["default_samplerate"]),
                    channels=min(2, max(1, int(output_info["max_output_channels"]) or 1)),
                    loopback=True,
                )

                mic_ok = False
                sys_ok = False

                try:
                    self.mic_writer.start()
                    mic_ok = True
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Mic recording start failed: %s", exc)

                try:
                    self.sys_writer.start()
                    sys_ok = True
                except Exception as exc:  # noqa: BLE001
                    if str(exc) == "wasapi_loopback_unsupported":
                        logger.warning("System audio capture unavailable (WASAPI loopback unsupported).")
                    else:
                        logger.exception("System recording start failed: %s", exc)

                if not mic_ok and not sys_ok:
                    self._stop_writer(self.mic_writer)
                    self._stop_writer(self.sys_writer)
                    self._reset_state()
                    return RecordingResult(ok=False, call_id=call_id, reason="recording_start_failed")

                self.is_active = True
                self.active_call_id = call_id
                self.active_phone_digits = phone_digits
                self.started_monotonic = time.monotonic()
                self.mic_path = str(mic_path) if mic_ok else None
                self.sys_path = str(sys_path) if sys_ok else None

                if not mic_ok:
                    self.mic_writer = None
                    self.mic_path = None
                if not sys_ok:
                    self.sys_writer = None
                    self.sys_path = None

                return RecordingResult(
                    ok=True,
                    call_id=call_id,
                    mic_path=self.mic_path,
                    sys_path=self.sys_path,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Recording start failed: %s", exc)
                self._stop_writer(self.mic_writer)
                self._stop_writer(self.sys_writer)
                self._reset_state()
                return RecordingResult(ok=False, call_id=call_id, reason=str(exc))

    def stop(self, call_id: int) -> RecordingResult:
        with self._lock:
            if not self.is_active or self.active_call_id is None:
                return RecordingResult(ok=False, call_id=call_id, reason="not_active")

            if call_id != self.active_call_id:
                return RecordingResult(ok=False, call_id=call_id, reason="call_id_mismatch")

            mic_writer = self.mic_writer
            sys_writer = self.sys_writer
            mic_path = self.mic_path
            sys_path = self.sys_path
            started = self.started_monotonic
            current_call_id = self.active_call_id

            self._reset_state()

            stop_errors: list[str] = []
            for writer, label in ((mic_writer, "mic"), (sys_writer, "system")):
                if not writer:
                    continue
                try:
                    writer.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("%s recording stop failed: %s", label, exc)
                    stop_errors.append(label)

            if stop_errors:
                return RecordingResult(ok=False, call_id=call_id, reason="stop_failed")

            duration_sec = None
            if started is not None:
                duration_sec = max(0, int(round(time.monotonic() - started)))

            return RecordingResult(
                ok=True,
                call_id=current_call_id,
                mic_path=mic_path,
                sys_path=sys_path,
                duration_sec=duration_sec,
            )

    def is_active_for_call(self, call_id: int) -> bool:
        with self._lock:
            return bool(self.is_active and self.active_call_id == call_id)

    def status(self, call_id: Optional[int] = None) -> dict:
        with self._lock:
            if not self.is_active or self.active_call_id is None:
                recording_active = bool(self.is_active and self.active_call_id is not None)
                return {"recording_active": recording_active, "call_id": None, "reason": "not_active"}
            if call_id is not None and call_id != self.active_call_id:
                recording_active = bool(self.is_active and self.active_call_id == call_id)
                return {
                    "recording_active": recording_active,
                    "call_id": self.active_call_id,
                    "reason": "call_id_mismatch",
                }
            recording_active = bool(self.is_active and self.active_call_id is not None)
            return {
                "recording_active": recording_active,
                "call_id": self.active_call_id,
                "audio_paths": {
                    "mic_path": self.mic_path,
                    "sys_path": self.sys_path,
                },
            }
