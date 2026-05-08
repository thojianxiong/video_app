from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np


@dataclass(frozen=True)
class FrameSample:
    timestamp_seconds: float
    frame_rgb: np.ndarray


def _resolve_ffmpeg_executable() -> str | None:
    configured = os.getenv("FFMPEG_PATH")
    if configured:
        return configured

    in_path = shutil.which("ffmpeg")
    if in_path:
        return in_path

    try:
        import imageio_ffmpeg  # type: ignore

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return bundled
    except Exception:
        return None

    return None


def resolve_ffmpeg_executable() -> str | None:
    return _resolve_ffmpeg_executable()


def _estimate_video_duration_seconds(video_path: Path) -> float:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return 0.0
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps > 0 and frame_count > 0:
            duration = frame_count / fps
            if duration > 0:
                return float(duration)
        return 0.0
    finally:
        capture.release()


def compute_video_signature(video_path: Path) -> str:
    file_stat = video_path.stat()
    fingerprint = f"{video_path.name}:{file_stat.st_size}:{file_stat.st_mtime_ns}"
    return hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()


def iter_video_frames(video_path: Path, interval_seconds: float = 2.0):
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be > 0")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 30.0

    frame_index = 0
    next_capture_at = 0.0

    try:
        while True:
            has_frame, frame_bgr = capture.read()
            if not has_frame:
                break

            timestamp_seconds = frame_index / fps
            if timestamp_seconds + (0.5 / fps) >= next_capture_at:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                yield FrameSample(
                    timestamp_seconds=float(timestamp_seconds),
                    frame_rgb=frame_rgb,
                )
                next_capture_at += interval_seconds

            frame_index += 1
    finally:
        capture.release()


def save_thumbnail(
    frame_rgb: np.ndarray,
    output_dir: Path,
    video_stem: str,
    timestamp_seconds: float,
    max_width: int = 320,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_video_stem = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in video_stem
    )
    milliseconds = int(round(timestamp_seconds * 1000))
    thumbnail_name = f"{safe_video_stem}_{milliseconds:09d}.jpg"
    thumbnail_path = output_dir / thumbnail_name

    height, width = frame_rgb.shape[:2]
    if width > max_width:
        resized_height = int(height * (max_width / width))
        frame_rgb = cv2.resize(
            frame_rgb,
            (max_width, max(1, resized_height)),
            interpolation=cv2.INTER_AREA,
        )

    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(
        str(thumbnail_path),
        frame_bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), 86],
    )
    return thumbnail_path


def generate_preview_thumbnail(
    video_path: Path,
    output_path: Path,
    max_width: int = 320,
) -> bool:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return False

    try:
        has_frame, frame_bgr = capture.read()
        if not has_frame or frame_bgr is None:
            return False

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        height, width = frame_rgb.shape[:2]
        if width > max_width:
            resized_height = int(height * (max_width / width))
            frame_rgb = cv2.resize(
                frame_rgb,
                (max_width, max(1, resized_height)),
                interpolation=cv2.INTER_AREA,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        success = cv2.imwrite(
            str(output_path),
            frame_bgr,
            [int(cv2.IMWRITE_JPEG_QUALITY), 84],
        )
        return bool(success)
    finally:
        capture.release()


def _run_ffmpeg_with_progress(
    command: list[str],
    *,
    duration_seconds: float,
    phase: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> tuple[int, str]:
    if not command or len(command) < 2:
        return 1, "invalid ffmpeg command"

    command_with_progress = list(command[:-1]) + ["-progress", "pipe:2", "-nostats", command[-1]]
    process = subprocess.Popen(
        command_with_progress,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
    )

    log_lines: list[str] = []
    max_log_lines = 300
    last_percent = -1.0
    last_emit_monotonic = 0.0

    def emit_progress(percent: float, *, force: bool = False) -> None:
        nonlocal last_percent, last_emit_monotonic
        if progress_callback is None:
            return
        safe_percent = max(0.0, min(100.0, float(percent)))
        now = time.monotonic()
        should_emit = force or safe_percent >= 100.0
        if not should_emit:
            should_emit = (
                safe_percent >= (last_percent + 1.0)
                or (now - last_emit_monotonic) >= 0.8
            )
        if not should_emit:
            return
        last_percent = safe_percent
        last_emit_monotonic = now
        try:
            progress_callback(safe_percent, phase)
        except Exception:
            # Never fail conversion because of a UI progress callback issue.
            return

    emit_progress(0.0, force=True)

    if process.stderr is not None:
        for raw_line in process.stderr:
            line = str(raw_line or "").strip()
            if not line:
                continue

            is_progress_line = "=" in line
            if line.startswith("out_time_ms="):
                raw_value = line.split("=", 1)[1].strip()
                try:
                    out_time_ms = int(raw_value)
                except ValueError:
                    out_time_ms = -1
                if out_time_ms >= 0 and duration_seconds > 0:
                    elapsed_seconds = float(out_time_ms) / 1_000_000.0
                    emit_progress((elapsed_seconds / duration_seconds) * 100.0)
            elif line.startswith("progress="):
                progress_state = line.split("=", 1)[1].strip().lower()
                if progress_state == "end":
                    emit_progress(100.0, force=True)

            if not is_progress_line:
                log_lines.append(line)
                if len(log_lines) > max_log_lines:
                    log_lines.pop(0)

    return_code = process.wait()
    emit_progress(100.0, force=True)
    return return_code, "\n".join(log_lines).strip()


def convert_to_mp4(
    input_path: Path,
    output_path: Path,
    progress_callback: Callable[[float, str], None] | None = None,
) -> tuple[bool, str]:
    """
    Converts any video to MP4 using ffmpeg while preserving audio.
    Strategy:
      1) Try stream-copy remux first (fast, no quality loss)
      2) Fallback to high-quality H.264 + AAC transcode
    Returns (success, error_message).
    """
    resolved_ffmpeg = _resolve_ffmpeg_executable()
    if not resolved_ffmpeg:
        return (
            False,
            "ffmpeg executable not found. Install ffmpeg, set FFMPEG_PATH, "
            "or install imageio-ffmpeg in the active environment.",
        )

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration_seconds = _estimate_video_duration_seconds(input_path)

        remux_command = [
            resolved_ffmpeg,
            "-y",
            "-err_detect",
            "ignore_err",
            "-fflags",
            "+genpts",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-dn",
            "-sn",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        remux_returncode, remux_error = _run_ffmpeg_with_progress(
            remux_command,
            duration_seconds=duration_seconds,
            phase="remux",
            progress_callback=progress_callback,
        )
        if remux_returncode == 0 and output_path.exists():
            print(
                f"[convert] mode=remux input={input_path.name} output={output_path.name}"
            )
            return True, ""

        output_path.unlink(missing_ok=True)

        transcode_command = [
            resolved_ffmpeg,
            "-y",
            "-err_detect",
            "ignore_err",
            "-fflags",
            "+genpts",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-dn",
            "-sn",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        transcode_returncode, transcode_error = _run_ffmpeg_with_progress(
            transcode_command,
            duration_seconds=duration_seconds,
            phase="transcode",
            progress_callback=progress_callback,
        )
        if transcode_returncode != 0 or not output_path.exists():
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            combined_error = transcode_error or remux_error
            if combined_error:
                return False, combined_error
            return (
                False,
                "ffmpeg failed remux and transcode without stderr output",
            )

        print(
            f"[convert] mode=transcode input={input_path.name} output={output_path.name} "
            "video=libx264(crf=18,preset=fast) audio=aac(192k)"
        )
        return True, ""
    except Exception as exc:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        return False, str(exc)
