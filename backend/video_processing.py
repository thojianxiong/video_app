from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

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


def convert_to_mp4(input_path: Path, output_path: Path) -> tuple[bool, str]:
    """
    Converts any video to MP4 using ffmpeg.
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
        command = [
            resolved_ffmpeg,
            "-y",
            "-err_detect",
            "ignore_err",
            "-fflags",
            "+genpts",
            "-i",
            str(input_path),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        stderr_output = (completed.stderr or "").strip()
        if completed.returncode != 0 or not output_path.exists():
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            if stderr_output:
                return False, stderr_output
            return False, f"ffmpeg exited with code {completed.returncode}"
        return True, ""
    except Exception as exc:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        return False, str(exc)
