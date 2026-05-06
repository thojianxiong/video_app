from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from backend.video_processing import resolve_ffmpeg_executable


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalize(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values.astype(np.float32)
    max_value = float(np.max(values))
    if not math.isfinite(max_value) or max_value <= 1e-9:
        return np.zeros_like(values, dtype=np.float32)
    return (values / max_value).astype(np.float32)


def _pad_or_trim(values: np.ndarray, size: int) -> np.ndarray:
    if size <= 0:
        return np.empty((0,), dtype=np.float32)
    if values.size == size:
        return values.astype(np.float32)
    if values.size > size:
        return values[:size].astype(np.float32)
    output = np.zeros((size,), dtype=np.float32)
    output[: values.size] = values.astype(np.float32)
    return output


def _top_peaks(
    values: np.ndarray,
    *,
    bucket_seconds: float,
    top_k: int = 16,
    min_gap_seconds: float = 1.5,
    min_intensity: float = 0.10,
    min_prominence: float = 0.02,
) -> list[dict[str, float]]:
    if values.size == 0 or top_k <= 0:
        return []

    safe_values = values.astype(np.float32)
    if safe_values.size >= 3:
        smooth_values = np.convolve(
            safe_values,
            np.array([0.25, 0.5, 0.25], dtype=np.float32),
            mode="same",
        )
    else:
        smooth_values = safe_values

    min_gap_buckets = max(1, int(round(float(min_gap_seconds) / float(bucket_seconds))))
    candidates: list[tuple[int, float, float, float]] = []
    for index in range(int(smooth_values.size)):
        center = float(smooth_values[index])
        if center < float(min_intensity):
            continue
        if index == 0:
            left = center
            right = float(smooth_values[index + 1]) if smooth_values.size > 1 else center
            is_local_max = center > right
        elif index == int(smooth_values.size) - 1:
            left = float(smooth_values[index - 1])
            right = center
            is_local_max = center > left
        else:
            left = float(smooth_values[index - 1])
            right = float(smooth_values[index + 1])
            is_local_max = center >= left and center >= right and (center > left or center > right)
        if not is_local_max:
            continue

        prominence = center - max(left, right)
        if prominence < float(min_prominence) and center < (float(min_intensity) * 1.8):
            continue

        raw_intensity = float(safe_values[index])
        score = raw_intensity + (max(0.0, prominence) * 0.65)
        candidates.append((index, raw_intensity, float(prominence), float(score)))

    if not candidates:
        order = np.argsort(safe_values)[::-1]
        for index in order.tolist():
            value = float(safe_values[index])
            if value < float(min_intensity):
                break
            candidates.append((int(index), value, 0.0, value))
            if len(candidates) >= int(top_k):
                break

    candidates.sort(key=lambda item: item[3], reverse=True)
    selected: list[int] = []
    peaks: list[dict[str, float]] = []
    for index, value, prominence, _score in candidates:
        if any(abs(index - existing) < min_gap_buckets for existing in selected):
            continue
        selected.append(index)
        peaks.append(
            {
                "bucket_index": float(index),
                "timestamp_seconds": float(index) * float(bucket_seconds),
                "intensity": float(value),
                "prominence": float(max(0.0, prominence)),
            }
        )
        if len(peaks) >= int(top_k):
            break
    return peaks


def _duration_seconds(video_path: Path) -> float:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return 0.0
    try:
        fps = _safe_float(capture.get(cv2.CAP_PROP_FPS), 0.0)
        frame_count = _safe_float(capture.get(cv2.CAP_PROP_FRAME_COUNT), 0.0)
        if fps > 0 and frame_count > 0:
            return float(frame_count / fps)
        return 0.0
    finally:
        capture.release()


def _compute_motion_intensity(
    video_path: Path,
    *,
    bucket_seconds: float,
    sample_fps: float = 3.0,
) -> tuple[np.ndarray, float]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return np.empty((0,), dtype=np.float32), 0.0

    fps = _safe_float(capture.get(cv2.CAP_PROP_FPS), 0.0)
    if fps <= 0:
        fps = 30.0
    sample_step = max(1, int(round(float(fps) / max(0.5, float(sample_fps)))))

    bucket_sums: dict[int, float] = {}
    bucket_counts: dict[int, int] = {}
    frame_index = 0
    previous_gray: np.ndarray | None = None

    try:
        while True:
            ok, frame_bgr = capture.read()
            if not ok:
                break
            if frame_index % sample_step != 0:
                frame_index += 1
                continue

            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
            if previous_gray is not None:
                diff = cv2.absdiff(gray, previous_gray)
                score = float(np.mean(diff)) / 255.0
                timestamp_seconds = float(frame_index) / float(fps)
                bucket_index = int(timestamp_seconds // float(bucket_seconds))
                bucket_sums[bucket_index] = bucket_sums.get(bucket_index, 0.0) + score
                bucket_counts[bucket_index] = bucket_counts.get(bucket_index, 0) + 1
            previous_gray = gray
            frame_index += 1
    finally:
        capture.release()

    duration_seconds = float(frame_index) / float(fps) if frame_index > 0 else 0.0
    max_bucket = max(bucket_sums.keys(), default=-1)
    bucket_count = max(1, int(math.ceil(duration_seconds / float(bucket_seconds))), max_bucket + 1)
    motion = np.zeros((bucket_count,), dtype=np.float32)
    for bucket_index, total in bucket_sums.items():
        count = bucket_counts.get(bucket_index, 0)
        if count > 0:
            motion[bucket_index] = float(total / count)
    return motion, duration_seconds


def _load_detection_counts(
    *,
    metadata_path: Path,
    video_filename: str,
    bucket_seconds: float,
    bucket_count: int,
    kind: str | None = None,
) -> np.ndarray:
    counts = np.zeros((bucket_count,), dtype=np.float32)
    if not metadata_path.exists():
        return counts

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return counts

    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return counts

    normalized_kind = str(kind).strip().lower() if kind else ""
    for item in entries:
        if not isinstance(item, dict):
            continue
        item_filename = str(item.get("video_filename", "")).strip()
        if item_filename != video_filename:
            continue
        if normalized_kind:
            item_kind = str(item.get("kind", "")).strip().lower()
            if item_kind != normalized_kind:
                continue
        timestamp = _safe_float(item.get("timestamp_seconds"), -1.0)
        if timestamp < 0:
            continue
        bucket_index = int(timestamp // float(bucket_seconds))
        if 0 <= bucket_index < bucket_count:
            counts[bucket_index] += 1.0
    return counts


def _compute_audio_intensity(
    video_path: Path,
    *,
    bucket_seconds: float,
) -> tuple[np.ndarray, str]:
    ffmpeg_path = resolve_ffmpeg_executable()
    if not ffmpeg_path:
        return np.empty((0,), dtype=np.float32), "ffmpeg unavailable"

    sample_rate = 16000
    command = [
        ffmpeg_path,
        "-v",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "-",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=False,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or b"").decode("utf-8", errors="ignore").strip()
        if not message:
            message = "audio decode failed"
        return np.empty((0,), dtype=np.float32), message

    raw_bytes = completed.stdout or b""
    if not raw_bytes:
        return np.empty((0,), dtype=np.float32), "no audio stream"

    samples = np.frombuffer(raw_bytes, dtype=np.int16)
    if samples.size == 0:
        return np.empty((0,), dtype=np.float32), "no audio stream"

    audio = samples.astype(np.float32) / 32768.0
    bucket_samples = max(1, int(round(float(sample_rate) * float(bucket_seconds))))
    bucket_count = int(math.ceil(float(audio.size) / float(bucket_samples)))
    values = np.zeros((bucket_count,), dtype=np.float32)
    for bucket_index in range(bucket_count):
        start = bucket_index * bucket_samples
        end = min(audio.size, start + bucket_samples)
        chunk = audio[start:end]
        if chunk.size == 0:
            continue
        values[bucket_index] = float(math.sqrt(float(np.mean(np.square(chunk)))))
    return values, "ok"


def build_video_triage_payload(
    *,
    video_path: Path,
    video_filename: str,
    bucket_seconds: float,
    face_people_metadata_path: Path,
    vehicles_metadata_path: Path,
    face_people_processed: bool,
    vehicles_processed: bool,
    peak_limit: int = 16,
) -> dict[str, Any]:
    safe_bucket_seconds = max(0.5, float(bucket_seconds))

    motion_raw, motion_duration = _compute_motion_intensity(
        video_path,
        bucket_seconds=safe_bucket_seconds,
    )
    audio_raw, audio_status = _compute_audio_intensity(
        video_path,
        bucket_seconds=safe_bucket_seconds,
    )

    duration_seconds = max(
        _duration_seconds(video_path),
        motion_duration,
        float(audio_raw.size) * safe_bucket_seconds,
    )
    bucket_count = max(
        1,
        int(math.ceil(duration_seconds / safe_bucket_seconds)),
        int(motion_raw.size),
        int(audio_raw.size),
    )

    people_raw = _load_detection_counts(
        metadata_path=face_people_metadata_path,
        video_filename=video_filename,
        bucket_seconds=safe_bucket_seconds,
        bucket_count=bucket_count,
        kind="people",
    )
    vehicles_raw = _load_detection_counts(
        metadata_path=vehicles_metadata_path,
        video_filename=video_filename,
        bucket_seconds=safe_bucket_seconds,
        bucket_count=bucket_count,
        kind="vehicle",
    )

    motion_norm = _normalize(_pad_or_trim(motion_raw, bucket_count))
    people_norm = _normalize(people_raw)
    vehicles_norm = _normalize(vehicles_raw)
    audio_norm = _normalize(_pad_or_trim(audio_raw, bucket_count))
    activity_norm = np.clip(
        (motion_norm + people_norm + vehicles_norm) / 3.0,
        0.0,
        1.0,
    ).astype(np.float32)

    activity_peaks = _top_peaks(
        activity_norm,
        bucket_seconds=safe_bucket_seconds,
        top_k=peak_limit,
        min_gap_seconds=1.5,
        min_intensity=0.12,
        min_prominence=0.02,
    )
    audio_peaks = _top_peaks(
        audio_norm,
        bucket_seconds=safe_bucket_seconds,
        top_k=peak_limit,
        min_gap_seconds=1.25,
        min_intensity=0.08,
        min_prominence=0.015,
    )

    return {
        "video_filename": video_filename,
        "bucket_seconds": safe_bucket_seconds,
        "duration_seconds": float(duration_seconds),
        "bucket_count": int(bucket_count),
        "activity_timeline": {
            "values": activity_norm.astype(np.float32).tolist(),
            "max": float(np.max(activity_norm) if activity_norm.size else 0.0),
        },
        "audio_timeline": {
            "values": audio_norm.astype(np.float32).tolist(),
            "max": float(np.max(audio_norm) if audio_norm.size else 0.0),
            "status": "ok" if audio_status == "ok" else "unavailable",
            "message": "" if audio_status == "ok" else str(audio_status),
        },
        "components": {
            "motion": motion_norm.astype(np.float32).tolist(),
            "people": people_norm.astype(np.float32).tolist(),
            "vehicles": vehicles_norm.astype(np.float32).tolist(),
        },
        "peaks": {
            "activity": activity_peaks,
            "audio": audio_peaks,
        },
        "analysis_available": {
            "face_people": bool(face_people_processed),
            "vehicles": bool(vehicles_processed),
        },
    }
