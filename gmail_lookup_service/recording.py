from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import sounddevice as sd
import soundfile as sf

logger = logging.getLogger("gmail_lookup")


@dataclass
class RecordingResult:
    ok: bool
    mic_path: Optional[str] = None
    sys_path: Optional[str] = None
    error: Optional[str] = None


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
        self.active = False
        self.mic_writer: Optional[_StreamWriter] = None
        self.sys_writer: Optional[_StreamWriter] = None
        self.current_result: Optional[RecordingResult] = None

    def start(self, phone_digits: str) -> RecordingResult:
        if self.active:
            return self.current_result or RecordingResult(ok=False, error="already_recording")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{ts}_{phone_digits}"
        mic_path = self.recordings_dir / f"{base}_mic.wav"
        sys_path = self.recordings_dir / f"{base}_system.wav"

        try:
            default_input = sd.default.device[0]
            default_output = sd.default.device[1]
            input_info = sd.query_devices(default_input, "input")
            output_info = sd.query_devices(default_output, "output")

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
                self.active = False
                self.current_result = RecordingResult(ok=False, error="recording_start_failed")
                return self.current_result

            self.active = True
            self.current_result = RecordingResult(
                ok=True,
                mic_path=str(mic_path) if mic_ok else None,
                sys_path=str(sys_path) if sys_ok else None,
            )
            return self.current_result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Recording start failed: %s", exc)
            self.active = False
            self.current_result = RecordingResult(ok=False, error=str(exc))
            return self.current_result

    def stop(self) -> RecordingResult:
        if not self.active:
            return self.current_result or RecordingResult(ok=False, error="not_recording")

        if self.mic_writer:
            self.mic_writer.stop()
        if self.sys_writer:
            self.sys_writer.stop()

        self.active = False
        return self.current_result or RecordingResult(ok=True)
