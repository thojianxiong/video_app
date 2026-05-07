from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote

import numpy as np
import cv2
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from backend.analysis import AnalysisSelection, VideoAnalyzer
from backend.analysis_store import AnalysisCropStore
from backend.embeddings import OpenCLIPEmbedder
from backend.routers.cases import build_cases_router
from backend.routers.embedding_settings import build_embedding_settings_router
from backend.routers.insights import build_insights_router
from backend.routers.media import build_media_router
from backend.routers.process_control import build_process_control_router
from backend.services.case_service import (
    CasePaths,
    build_case_paths as _build_case_paths_impl,
    create_case_sync as _create_case_sync_impl,
    delete_case_sync as _delete_case_sync_impl,
    ensure_case_directories as _ensure_case_directories_impl,
    get_case_paths_or_raise as _get_case_paths_or_raise_impl,
    list_cases_sync as _list_cases_sync_impl,
    normalize_case_id as _normalize_case_id_impl,
    rename_case_sync as _rename_case_sync_impl,
    resolve_case_id_or_default as _resolve_case_id_or_default_impl,
    utc_now_iso as _utc_now_iso_impl,
)
from backend.services.embedding_settings_service import (
    DEFAULT_OPENCLIP_DEVICE,
    DEFAULT_OPENCLIP_MODEL,
    DEFAULT_OPENCLIP_PRETRAINED,
    EMBEDDING_DEVICE_OPTIONS,
    EMBEDDING_MODEL_PROFILES,
    build_embedding_settings_response_sync as _build_embedding_settings_response_sync_impl,
    read_saved_embedding_settings_sync as _read_saved_embedding_settings_sync_impl,
    resolve_effective_embedding_settings_sync as _resolve_effective_embedding_settings_sync_impl,
    write_saved_embedding_settings_sync as _write_saved_embedding_settings_sync_impl,
)
from backend.services.insights_service import InsightsService
from backend.services.media_service import MediaService
from backend.services.process_control_service import ProcessControlService
from backend.stores.index_job_store import IndexJobStore
from backend.stores.index_queue_store import IndexQueueStore
from backend.stores.upload_session_store import UploadSessionStore
from backend.stores.video_pipeline_store import VideoPipelineStore
from backend.temporal_store import TemporalWindowStore
from backend.triage import build_video_triage_payload
from backend.vector_store import VectorStore
from backend.video_processing import (
    compute_video_signature,
    convert_to_mp4,
    generate_preview_thumbnail,
    iter_video_frames,
    save_thumbnail,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
CASES_DIR = BASE_DIR / "cases"
CASES_REGISTRY_PATH = CASES_DIR / "cases.json"
APP_SETTINGS_PATH = CASES_DIR / "app_settings.json"
INDEX_JOBS_DB_PATH = CASES_DIR / "index_jobs.db"
INDEX_QUEUE_DB_PATH = CASES_DIR / "index_queue.db"
VIDEO_PIPELINE_DB_PATH = CASES_DIR / "video_pipeline.db"
UPLOAD_SESSIONS_DB_PATH = CASES_DIR / "upload_sessions.db"

SEMANTIC_OBJECT = "object"
SEMANTIC_ACTION = "action"
SEMANTIC_SCENE = "scene"
SEMANTIC_INTENT_OPTIONS = [SEMANTIC_OBJECT, SEMANTIC_ACTION, SEMANTIC_SCENE]
TRIAGE_CACHE_VERSION = 2

INTENT_PROMPTS = {
    SEMANTIC_OBJECT: [
        "a specific object or person appearance in a single frame",
        "an identifiable thing in a video frame",
        "a close visual match for an object",
    ],
    SEMANTIC_ACTION: [
        "an action happening across time in video",
        "a person or vehicle performing an activity",
        "an event unfolding over consecutive moments",
    ],
    SEMANTIC_SCENE: [
        "an overall place, environment, or scene context",
        "the broader setting of a surveillance camera view",
        "a location-level visual context",
    ],
}

ACTION_KEYWORDS = {
    "run", "running", "walk", "walking", "jog", "jogging", "sprint", "chase", "follow",
    "fight", "fighting", "hit", "punch", "kick", "fall", "falling", "trip", "slip",
    "shoot", "shooting", "draw", "drawing", "aim", "pointing", "grab", "snatch",
    "steal", "stealing", "attack", "approach", "approaching", "leave", "leaving",
    "enter", "entering", "exit", "exiting", "drive", "driving", "park", "parking",
    "crash", "u-turn", "turn", "loading", "unloading", "board", "boarding",
}

SCENE_KEYWORDS = {
    "street", "road", "highway", "alley", "junction", "intersection", "crosswalk",
    "station", "platform", "bus", "busstop", "mrt", "subway", "train", "airport",
    "mall", "shop", "store", "office", "room", "corridor", "hallway", "lobby",
    "parking", "carpark", "garage", "outdoor", "indoor", "night", "day", "daytime",
    "crowd", "crowded", "traffic", "residential", "apartment", "building",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}
CASE_REGISTRY_LOCK = Lock()
APP_SETTINGS_LOCK = Lock()

for path in (FRONTEND_DIR, CASES_DIR):
    path.mkdir(parents=True, exist_ok=True)


async def _startup_application(application: FastAPI) -> None:
    embedding_settings = await asyncio.to_thread(_resolve_effective_embedding_settings_sync)
    embedder = await asyncio.to_thread(
        OpenCLIPEmbedder,
        model_name=embedding_settings["model_name"],
        pretrained=embedding_settings["pretrained"],
        cache_dir=os.getenv("OPENCLIP_CACHE_DIR"),
        device_preference=embedding_settings["device_preference"],
    )
    analyzer = await asyncio.to_thread(
        VideoAnalyzer,
        os.getenv("YOLO_MODEL_PATH"),
        _float_from_env("YOLO_CONFIDENCE", 0.3),
        _float_from_env("YOLO_IOU", 0.45),
    )
    application.state.embedder = embedder
    application.state.analyzer = analyzer
    application.state.vector_stores = {}
    application.state.vector_stores_lock = Lock()
    application.state.temporal_stores = {}
    application.state.temporal_stores_lock = Lock()
    application.state.analysis_stores = {}
    application.state.analysis_stores_lock = Lock()
    application.state.index_jobs = {}
    application.state.index_jobs_lock = Lock()
    application.state.index_tasks = {}
    index_job_store = await asyncio.to_thread(IndexJobStore, INDEX_JOBS_DB_PATH)
    application.state.index_job_store = index_job_store
    index_queue_store = await asyncio.to_thread(IndexQueueStore, INDEX_QUEUE_DB_PATH)
    application.state.index_queue_store = index_queue_store
    video_pipeline_store = await asyncio.to_thread(VideoPipelineStore, VIDEO_PIPELINE_DB_PATH)
    application.state.video_pipeline_store = video_pipeline_store
    upload_session_store = await asyncio.to_thread(UploadSessionStore, UPLOAD_SESSIONS_DB_PATH)
    application.state.upload_session_store = upload_session_store
    application.state.upload_session_chunk_lock = Lock()

    interrupted_jobs = await asyncio.to_thread(index_job_store.mark_incomplete_jobs_interrupted)
    interrupted_queue_jobs = await asyncio.to_thread(index_queue_store.mark_running_jobs_interrupted)
    interrupted_pipeline = await asyncio.to_thread(video_pipeline_store.mark_running_as_interrupted)
    raw_snapshots = await asyncio.to_thread(index_job_store.load_all_snapshots)
    restored_jobs: dict[str, dict] = {}
    if isinstance(raw_snapshots, dict):
        for raw_case_id, raw_job in raw_snapshots.items():
            case_id = str(raw_case_id or "").strip()
            if not case_id or not isinstance(raw_job, dict):
                continue
            restored_jobs[case_id] = _index_job_snapshot(raw_job, case_id=case_id)
    application.state.index_jobs = restored_jobs

    application.state.shutdown_requested = False
    application.state.shutdown_requested_at = ""
    application.state.embedding_settings = embedding_settings
    application.state.intent_prompt_embeddings = _build_intent_prompt_embeddings(embedder)
    print(
        f"[startup] OpenCLIP model={embedder.model_name} "
        f"pretrained={embedder.pretrained} "
        f"device={embedder.device} "
        f"device_preference={embedder.device_preference}"
    )
    if interrupted_jobs > 0:
        print(f"[startup] Marked {interrupted_jobs} incomplete index job(s) as interrupted.")
    if interrupted_queue_jobs > 0:
        print(f"[startup] Marked {interrupted_queue_jobs} running queued job(s) as interrupted.")
    if interrupted_pipeline > 0:
        print(f"[startup] Marked {interrupted_pipeline} running pipeline stage(s) as interrupted.")
    if restored_jobs:
        print(f"[startup] Restored {len(restored_jobs)} persisted index job snapshot(s).")
    await asyncio.to_thread(_list_cases_sync)
    application.state.index_queue_worker_task = asyncio.create_task(_index_queue_worker_loop())


@asynccontextmanager
async def _app_lifespan(application: FastAPI):
    await _startup_application(application)
    try:
        yield
    finally:
        worker_task = getattr(application.state, "index_queue_worker_task", None)
        if isinstance(worker_task, asyncio.Task):
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Local Video Semantic Search",
    version="1.0.0",
    lifespan=_app_lifespan,
)

app.mount("/media/cases", StaticFiles(directory=str(CASES_DIR)), name="media-cases")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def _read_saved_embedding_settings_sync() -> dict[str, str]:
    return _read_saved_embedding_settings_sync_impl(
        app_settings_path=APP_SETTINGS_PATH,
        app_settings_lock=APP_SETTINGS_LOCK,
        default_model=DEFAULT_OPENCLIP_MODEL,
        default_pretrained=DEFAULT_OPENCLIP_PRETRAINED,
        default_device=DEFAULT_OPENCLIP_DEVICE,
        device_options=EMBEDDING_DEVICE_OPTIONS,
    )


def _write_saved_embedding_settings_sync(
    *,
    model_name: str,
    pretrained: str,
    device_preference: str,
) -> dict[str, str]:
    return _write_saved_embedding_settings_sync_impl(
        app_settings_path=APP_SETTINGS_PATH,
        app_settings_lock=APP_SETTINGS_LOCK,
        model_name=model_name,
        pretrained=pretrained,
        device_preference=device_preference,
        default_model=DEFAULT_OPENCLIP_MODEL,
        default_pretrained=DEFAULT_OPENCLIP_PRETRAINED,
        default_device=DEFAULT_OPENCLIP_DEVICE,
        device_options=EMBEDDING_DEVICE_OPTIONS,
    )


def _resolve_effective_embedding_settings_sync(
    saved_settings: dict[str, str] | None = None,
) -> dict[str, str]:
    return _resolve_effective_embedding_settings_sync_impl(
        app_settings_path=APP_SETTINGS_PATH,
        app_settings_lock=APP_SETTINGS_LOCK,
        saved_settings=saved_settings,
        default_model=DEFAULT_OPENCLIP_MODEL,
        default_pretrained=DEFAULT_OPENCLIP_PRETRAINED,
        default_device=DEFAULT_OPENCLIP_DEVICE,
        device_options=EMBEDDING_DEVICE_OPTIONS,
    )


def _build_embedding_settings_response_sync() -> dict:
    embedder = getattr(app.state, "embedder", None)
    loaded_embedding = {
        "model_name": str(getattr(embedder, "model_name", "")),
        "pretrained": str(getattr(embedder, "pretrained", "")),
        "device_preference": str(
            getattr(embedder, "device_preference", "")
        ),
        "device": str(getattr(embedder, "device", "")),
    }
    return _build_embedding_settings_response_sync_impl(
        app_settings_path=APP_SETTINGS_PATH,
        app_settings_lock=APP_SETTINGS_LOCK,
        loaded_embedding=loaded_embedding,
        profiles=EMBEDDING_MODEL_PROFILES,
        device_options=EMBEDDING_DEVICE_OPTIONS,
        default_model=DEFAULT_OPENCLIP_MODEL,
        default_pretrained=DEFAULT_OPENCLIP_PRETRAINED,
        default_device=DEFAULT_OPENCLIP_DEVICE,
    )


def _normalize_embedding_vector(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(arr))
    if norm <= 0:
        return arr
    return (arr / norm).astype(np.float32)


def _average_embeddings(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        return np.empty((0,), dtype=np.float32)
    stacked = np.vstack([_normalize_embedding_vector(item) for item in vectors]).astype(np.float32)
    averaged = stacked.mean(axis=0).astype(np.float32)
    return _normalize_embedding_vector(averaged)


def _build_intent_prompt_embeddings(embedder: OpenCLIPEmbedder) -> dict[str, np.ndarray]:
    payload: dict[str, np.ndarray] = {}
    for intent, prompts in INTENT_PROMPTS.items():
        vectors: list[np.ndarray] = []
        for prompt in prompts:
            try:
                vectors.append(embedder.encode_text(prompt))
            except Exception:
                continue
        if vectors:
            payload[intent] = _average_embeddings(vectors)
    return payload


def _tokenize_query(text: str) -> set[str]:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return set()
    return {
        token
        for token in re.split(r"[^a-z0-9]+", normalized)
        if token
    }


def _detect_semantic_intent(query: str, query_embedding: np.ndarray) -> dict[str, Any]:
    normalized_query = str(query or "").strip()
    tokens = _tokenize_query(normalized_query)
    prompt_embeddings = getattr(app.state, "intent_prompt_embeddings", {}) or {}
    query_vec = _normalize_embedding_vector(query_embedding)

    scores: dict[str, float] = {intent: 0.0 for intent in SEMANTIC_INTENT_OPTIONS}
    reasons: dict[str, list[str]] = {intent: [] for intent in SEMANTIC_INTENT_OPTIONS}

    for intent in SEMANTIC_INTENT_OPTIONS:
        prompt_vec = prompt_embeddings.get(intent)
        if isinstance(prompt_vec, np.ndarray) and prompt_vec.size > 0:
            semantic_score = float(np.dot(query_vec, prompt_vec))
            scores[intent] += semantic_score
            reasons[intent].append(f"semantic={semantic_score:.3f}")

    action_hits = len(tokens.intersection(ACTION_KEYWORDS))
    scene_hits = len(tokens.intersection(SCENE_KEYWORDS))

    if action_hits > 0:
        boost = min(0.35, 0.12 * action_hits)
        scores[SEMANTIC_ACTION] += boost
        reasons[SEMANTIC_ACTION].append(f"action_kw={action_hits}")

    if scene_hits > 0:
        boost = min(0.35, 0.12 * scene_hits)
        scores[SEMANTIC_SCENE] += boost
        reasons[SEMANTIC_SCENE].append(f"scene_kw={scene_hits}")

    if len(tokens) <= 2 and action_hits == 0 and scene_hits == 0:
        scores[SEMANTIC_OBJECT] += 0.08
        reasons[SEMANTIC_OBJECT].append("short_query_object_bias")

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_intent, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else -1.0
    margin = float(best_score - second_score)

    if margin < 0.02 and best_intent != SEMANTIC_OBJECT:
        best_intent = SEMANTIC_OBJECT
        reasons[SEMANTIC_OBJECT].append("low_margin_default_object")

    return {
        "intent": best_intent,
        "scores": {key: float(value) for key, value in scores.items()},
        "margin": margin,
        "reasons": reasons.get(best_intent, []),
        "tokens": sorted(tokens),
    }


def _embedding_engine_info() -> dict[str, Any]:
    embedder: OpenCLIPEmbedder = app.state.embedder
    return {
        "model_name": str(getattr(embedder, "model_name", "")),
        "pretrained": str(getattr(embedder, "pretrained", "")),
        "device_preference": str(getattr(embedder, "device_preference", "")),
        "device": str(getattr(embedder, "device", "")),
        "embedding_dim": int(getattr(embedder, "embedding_dim", 0)),
    }


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    index_html = FRONTEND_DIR / "index.html"
    if not index_html.exists():
        raise HTTPException(status_code=500, detail="frontend/index.html not found")
    return FileResponse(str(index_html))


def _safe_upload_filename(filename: str) -> str:
    raw_name = Path(filename).name
    safe_name = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in raw_name
    )
    if not safe_name:
        safe_name = "uploaded_video.mp4"
    return safe_name


def _is_supported_video(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


def _normalize_case_id(case_id: str) -> str:
    return _normalize_case_id_impl(case_id)


def _build_case_paths(case_id: str) -> CasePaths:
    return _build_case_paths_impl(case_id, cases_dir=CASES_DIR)


def _ensure_case_directories(case_paths: CasePaths) -> None:
    _ensure_case_directories_impl(case_paths)


def _utc_now_iso() -> str:
    return _utc_now_iso_impl()


def _list_cases_sync() -> list[dict[str, str]]:
    return _list_cases_sync_impl(
        cases_registry_path=CASES_REGISTRY_PATH,
        cases_dir=CASES_DIR,
        case_registry_lock=CASE_REGISTRY_LOCK,
    )


def _create_case_sync(name: str) -> dict[str, str]:
    return _create_case_sync_impl(
        name,
        cases_registry_path=CASES_REGISTRY_PATH,
        cases_dir=CASES_DIR,
        case_registry_lock=CASE_REGISTRY_LOCK,
    )


def _delete_case_sync(case_id: str) -> dict[str, str]:
    return _delete_case_sync_impl(
        case_id,
        cases_registry_path=CASES_REGISTRY_PATH,
        cases_dir=CASES_DIR,
        case_registry_lock=CASE_REGISTRY_LOCK,
    )


def _rename_case_sync(case_id: str, name: str) -> dict[str, str]:
    return _rename_case_sync_impl(
        case_id,
        name,
        cases_registry_path=CASES_REGISTRY_PATH,
        cases_dir=CASES_DIR,
        case_registry_lock=CASE_REGISTRY_LOCK,
    )


def _get_case_paths_or_raise(case_id: str) -> CasePaths:
    return _get_case_paths_or_raise_impl(
        case_id,
        cases_registry_path=CASES_REGISTRY_PATH,
        cases_dir=CASES_DIR,
        case_registry_lock=CASE_REGISTRY_LOCK,
    )


def _resolve_case_id_or_default(case_id: str | None) -> str:
    return _resolve_case_id_or_default_impl(
        case_id,
        cases_registry_path=CASES_REGISTRY_PATH,
        cases_dir=CASES_DIR,
        case_registry_lock=CASE_REGISTRY_LOCK,
    )


def _list_case_video_filenames(case_paths: CasePaths) -> list[str]:
    output: list[str] = []
    for file_path in sorted(case_paths.videos_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        output.append(file_path.name)
    return output


def _resolve_index_filenames(
    case_paths: CasePaths,
    requested_filenames: list[str] | None,
) -> list[str]:
    available = set(_list_case_video_filenames(case_paths))
    if requested_filenames is None:
        resolved = sorted(available)
        if not resolved:
            raise ValueError("No videos available for indexing in this case.")
        return resolved

    resolved: list[str] = []
    seen: set[str] = set()
    for raw_name in requested_filenames:
        safe_name = Path(str(raw_name or "")).name.strip()
        if not safe_name or safe_name in seen:
            continue
        seen.add(safe_name)
        if safe_name not in available:
            raise FileNotFoundError(safe_name)
        resolved.append(safe_name)

    if not resolved:
        raise ValueError("No valid filenames provided for indexing.")
    return resolved


def _new_index_job_record(
    *,
    case_id: str,
    filenames: list[str],
    frame_interval_seconds: float,
    batch_size: int,
    force: bool,
) -> dict:
    now = _utc_now_iso()
    return {
        "case_id": case_id,
        "status": "queued",
        "running": True,
        "total": int(len(filenames)),
        "completed": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "indexed_frames": 0,
        "indexed_windows": 0,
        "current_filename": "",
        "current_video_processed_frames": 0,
        "current_video_total_frames": 0,
        "current_video_progress_percent": 0.0,
        "current_video_eta_seconds": None,
        "current_video_started_ts": 0.0,
        "filenames": list(filenames),
        "errors": [],
        "results": [],
        "cancel_requested": False,
        "frame_interval_seconds": float(frame_interval_seconds),
        "batch_size": int(batch_size),
        "force": bool(force),
        "embedding_engine": _embedding_engine_info(),
        "started_at": now,
        "updated_at": now,
        "finished_at": "",
    }


def _index_job_snapshot(job: dict | None, *, case_id: str) -> dict:
    if not isinstance(job, dict):
        return {
            "case_id": case_id,
            "status": "idle",
            "running": False,
            "total": 0,
            "completed": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "indexed_frames": 0,
            "indexed_windows": 0,
            "current_filename": "",
            "current_video_processed_frames": 0,
            "current_video_total_frames": 0,
            "current_video_progress_percent": 0.0,
            "current_video_eta_seconds": None,
            "frame_interval_seconds": 0.0,
            "batch_size": 0,
            "force": False,
            "embedding_engine": _embedding_engine_info(),
            "errors": [],
            "results": [],
            "filenames": [],
            "cancel_requested": False,
            "started_at": "",
            "updated_at": "",
            "finished_at": "",
            "progress_percent": 0.0,
        }

    total = max(0, int(job.get("total", 0)))
    completed = max(0, int(job.get("completed", 0)))
    progress_percent = (
        min(100.0, max(0.0, (float(completed) / float(total)) * 100.0))
        if total > 0
        else 0.0
    )
    current_video_processed_frames = max(0, int(job.get("current_video_processed_frames", 0)))
    current_video_total_frames = max(0, int(job.get("current_video_total_frames", 0)))
    current_video_progress_percent = float(job.get("current_video_progress_percent", 0.0))
    current_video_progress_percent = min(100.0, max(0.0, current_video_progress_percent))
    raw_eta = job.get("current_video_eta_seconds")
    current_video_eta_seconds = None
    if raw_eta is not None:
        try:
            current_video_eta_seconds = max(0.0, float(raw_eta))
        except (TypeError, ValueError):
            current_video_eta_seconds = None

    return {
        "case_id": case_id,
        "status": str(job.get("status", "idle")),
        "running": bool(job.get("running", False)),
        "total": total,
        "completed": completed,
        "processed": max(0, int(job.get("processed", 0))),
        "skipped": max(0, int(job.get("skipped", 0))),
        "failed": max(0, int(job.get("failed", 0))),
        "indexed_frames": max(0, int(job.get("indexed_frames", 0))),
        "indexed_windows": max(0, int(job.get("indexed_windows", 0))),
        "current_filename": str(job.get("current_filename") or ""),
        "current_video_processed_frames": current_video_processed_frames,
        "current_video_total_frames": current_video_total_frames,
        "current_video_progress_percent": current_video_progress_percent,
        "current_video_eta_seconds": current_video_eta_seconds,
        "frame_interval_seconds": float(job.get("frame_interval_seconds", 0.0)),
        "batch_size": max(0, int(job.get("batch_size", 0))),
        "force": bool(job.get("force", False)),
        "embedding_engine": dict(job.get("embedding_engine") or _embedding_engine_info()),
        "errors": [str(item) for item in (job.get("errors") or [])],
        "results": [item for item in (job.get("results") or []) if isinstance(item, dict)],
        "filenames": [str(item) for item in (job.get("filenames") or []) if str(item).strip()],
        "cancel_requested": bool(job.get("cancel_requested", False)),
        "started_at": str(job.get("started_at") or ""),
        "updated_at": str(job.get("updated_at") or ""),
        "finished_at": str(job.get("finished_at") or ""),
        "progress_percent": float(progress_percent),
    }


def _find_running_index_case_id_locked(jobs: dict[str, dict]) -> str | None:
    for candidate_case_id, candidate_job in jobs.items():
        status = str(candidate_job.get("status") or "")
        if bool(candidate_job.get("running")) or status in {"queued", "running"}:
            return str(candidate_case_id)
    return None


def _pipeline_store() -> VideoPipelineStore | None:
    store = getattr(app.state, "video_pipeline_store", None)
    if isinstance(store, VideoPipelineStore):
        return store
    return None


def _pipeline_update_stage_sync(
    *,
    case_id: str,
    filename: str,
    stage: str,
    status: str,
    error: str = "",
    details: dict | None = None,
    increment_attempt: bool = False,
    event: str = "",
) -> None:
    store = _pipeline_store()
    if store is None:
        return
    store.update_stage(
        case_id=case_id,
        filename=filename,
        stage=stage,
        status=status,
        error=error,
        details=details,
        increment_attempt=increment_attempt,
        event=event,
    )


async def _pipeline_update_stage(
    *,
    case_id: str,
    filename: str,
    stage: str,
    status: str,
    error: str = "",
    details: dict | None = None,
    increment_attempt: bool = False,
    event: str = "",
) -> None:
    try:
        await asyncio.to_thread(
            _pipeline_update_stage_sync,
            case_id=case_id,
            filename=filename,
            stage=stage,
            status=status,
            error=error,
            details=details,
            increment_attempt=increment_attempt,
            event=event,
        )
    except Exception as exc:
        print(
            f"[pipeline][{case_id}] update_stage_failed "
            f"file={filename} stage={stage} status={status} error={exc}"
        )


def _pipeline_set_metadata_sync(case_id: str, filename: str, metadata: dict) -> None:
    store = _pipeline_store()
    if store is None:
        return
    store.set_metadata(case_id, filename, metadata)


async def _pipeline_set_metadata(case_id: str, filename: str, metadata: dict) -> None:
    try:
        await asyncio.to_thread(_pipeline_set_metadata_sync, case_id, filename, metadata)
    except Exception as exc:
        print(f"[pipeline][{case_id}] metadata_failed file={filename} error={exc}")


def _persist_index_job_snapshot_sync(case_id: str) -> None:
    index_job_store = getattr(app.state, "index_job_store", None)
    if not isinstance(index_job_store, IndexJobStore):
        return

    normalized_case_id = str(case_id or "").strip()
    if not normalized_case_id:
        return

    jobs: dict[str, dict] = app.state.index_jobs
    lock: Lock = app.state.index_jobs_lock
    with lock:
        current = jobs.get(normalized_case_id)
        if not isinstance(current, dict):
            return
        snapshot = _index_job_snapshot(current, case_id=normalized_case_id)

    index_job_store.upsert_snapshot(snapshot)


async def _persist_index_job_snapshot(case_id: str) -> None:
    try:
        await asyncio.to_thread(_persist_index_job_snapshot_sync, case_id)
    except Exception as exc:
        print(f"[index-persist][{case_id}] failed error={exc}")


def _map_index_snapshot_to_queue_status(snapshot: dict) -> tuple[str, str]:
    status = str(snapshot.get("status") or "").strip().lower()
    if status in {"completed", "completed_with_errors"}:
        return "completed", ""
    if status in {"failed"}:
        errors = snapshot.get("errors") or []
        if isinstance(errors, list) and errors:
            return "failed", _truncate_error(str(errors[-1]))
        return "failed", "Background indexing failed."
    if status in {"cancelled", "cancelling"}:
        return "cancelled", "Background indexing cancelled."
    if status in {"interrupted"}:
        return "interrupted", "Background indexing interrupted."
    return "failed", f"Unexpected index job status: {status or 'unknown'}"


async def _index_queue_worker_loop() -> None:
    queue_store = getattr(app.state, "index_queue_store", None)
    if not isinstance(queue_store, IndexQueueStore):
        return

    while True:
        try:
            queued_job = await asyncio.to_thread(queue_store.claim_next_queued)
            if not isinstance(queued_job, dict):
                await asyncio.sleep(0.5)
                continue

            job_id = int(queued_job.get("job_id", 0))
            payload = queued_job.get("payload") or {}
            case_id = _normalize_case_id(str(queued_job.get("case_id") or payload.get("case_id") or ""))

            filenames = [str(item) for item in (payload.get("filenames") or []) if str(item).strip()]
            if not filenames:
                await asyncio.to_thread(
                    queue_store.complete_job,
                    job_id=job_id,
                    status="failed",
                    error="Queued job payload missing filenames.",
                )
                continue

            frame_interval_seconds = float(payload.get("frame_interval_seconds", 1.0))
            batch_size = int(payload.get("batch_size", 32))
            force = bool(payload.get("force", False))

            try:
                await asyncio.to_thread(_get_case_paths_or_raise, case_id)
            except Exception as exc:
                await asyncio.to_thread(
                    queue_store.complete_job,
                    job_id=job_id,
                    status="failed",
                    error=_truncate_error(f"Case validation failed: {exc}"),
                )
                continue

            with app.state.index_jobs_lock:
                job = _new_index_job_record(
                    case_id=case_id,
                    filenames=filenames,
                    frame_interval_seconds=frame_interval_seconds,
                    batch_size=batch_size,
                    force=force,
                )
                job["running"] = False
                job["status"] = "queued"
                job["queue_job_id"] = int(job_id)
                app.state.index_jobs[case_id] = job

            await _persist_index_job_snapshot(case_id)

            run_task = asyncio.create_task(_run_index_job_async(case_id))
            with app.state.index_jobs_lock:
                app.state.index_tasks[case_id] = run_task

            try:
                await run_task
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await asyncio.to_thread(
                    queue_store.complete_job,
                    job_id=job_id,
                    status="failed",
                    error=_truncate_error(str(exc)),
                )
                continue

            with app.state.index_jobs_lock:
                snapshot = _index_job_snapshot(app.state.index_jobs.get(case_id), case_id=case_id)

            queue_status, queue_error = _map_index_snapshot_to_queue_status(snapshot)
            await asyncio.to_thread(
                queue_store.complete_job,
                job_id=job_id,
                status=queue_status,
                error=queue_error,
            )
        except asyncio.CancelledError:
            return
        except Exception as exc:
            print(f"[index-queue] worker_error={exc}")
            await asyncio.sleep(0.5)


async def _run_index_job_async(case_id: str) -> None:
    jobs: dict[str, dict] = app.state.index_jobs
    lock: Lock = app.state.index_jobs_lock
    tasks: dict[str, asyncio.Task] = app.state.index_tasks
    normalized_case_id = _normalize_case_id(case_id)

    with lock:
        initial = jobs.get(normalized_case_id)
        if not isinstance(initial, dict):
            tasks.pop(normalized_case_id, None)
            return
        frame_interval_seconds = float(initial.get("frame_interval_seconds", 2.0))
        batch_size = int(initial.get("batch_size", 32))
        force = bool(initial.get("force", False))
        initial_filenames: list[str] = []
        initial_seen: set[str] = set()
        for item in (initial.get("filenames") or []):
            safe = str(item).strip()
            if not safe or safe in initial_seen:
                continue
            initial_seen.add(safe)
            initial_filenames.append(safe)
        initial["filenames"] = initial_filenames
        initial["total"] = len(initial_filenames)
        initial["status"] = "running"
        initial["running"] = True
        initial["updated_at"] = _utc_now_iso()

    await _persist_index_job_snapshot(normalized_case_id)

    try:
        next_index = 0
        while True:
            with lock:
                current = jobs.get(normalized_case_id)
                if not isinstance(current, dict):
                    return
                if bool(current.get("cancel_requested", False)):
                    raise asyncio.CancelledError()
                dynamic_filenames: list[str] = []
                dynamic_seen: set[str] = set()
                for item in (current.get("filenames") or []):
                    safe = str(item).strip()
                    if not safe or safe in dynamic_seen:
                        continue
                    dynamic_seen.add(safe)
                    dynamic_filenames.append(safe)
                current["filenames"] = dynamic_filenames
                current["total"] = len(dynamic_filenames)
                if next_index >= len(dynamic_filenames):
                    break
                filename = dynamic_filenames[next_index]
                next_index += 1
                current["current_filename"] = str(filename)
                current["current_video_processed_frames"] = 0
                current["current_video_total_frames"] = 0
                current["current_video_progress_percent"] = 0.0
                current["current_video_eta_seconds"] = None
                current["current_video_started_ts"] = float(time.time())
                current["updated_at"] = _utc_now_iso()

            await _pipeline_update_stage(
                case_id=normalized_case_id,
                filename=filename,
                stage="base_index",
                status="running",
                increment_attempt=True,
                event="background_index_started",
                details={
                    "source": "background_index",
                    "frame_interval_seconds": frame_interval_seconds,
                    "batch_size": batch_size,
                    "force": force,
                },
            )
            await _persist_index_job_snapshot(normalized_case_id)

            try:
                def _is_cancel_requested() -> bool:
                    with lock:
                        running_job = jobs.get(normalized_case_id)
                        if not isinstance(running_job, dict):
                            return True
                        return bool(running_job.get("cancel_requested", False))

                def _on_video_progress(processed_frames: int, estimated_total_frames: int | None) -> None:
                    with lock:
                        running_job = jobs.get(normalized_case_id)
                        if not isinstance(running_job, dict):
                            return
                        if str(running_job.get("current_filename") or "") != str(filename):
                            return
                        processed = max(0, int(processed_frames))
                        estimated = max(0, int(estimated_total_frames or 0))
                        if estimated < processed:
                            estimated = processed

                        running_job["current_video_processed_frames"] = processed
                        running_job["current_video_total_frames"] = estimated
                        if estimated > 0:
                            running_job["current_video_progress_percent"] = min(
                                100.0,
                                max(0.0, (float(processed) / float(estimated)) * 100.0),
                            )
                        else:
                            running_job["current_video_progress_percent"] = 0.0

                        started_ts = float(running_job.get("current_video_started_ts") or 0.0)
                        eta_seconds = None
                        if started_ts > 0 and processed > 0 and estimated > processed:
                            elapsed = max(0.001, float(time.time()) - started_ts)
                            rate = float(processed) / elapsed
                            if rate > 0:
                                eta_seconds = max(0.0, (float(estimated) - float(processed)) / rate)
                        elif estimated > 0 and processed >= estimated and processed > 0:
                            eta_seconds = 0.0
                        running_job["current_video_eta_seconds"] = eta_seconds
                        running_job["updated_at"] = _utc_now_iso()

                result = await asyncio.to_thread(
                    _process_video_sync,
                    case_id=normalized_case_id,
                    filename=filename,
                    frame_interval_seconds=frame_interval_seconds,
                    batch_size=batch_size,
                    force=force,
                    analysis_face_people=False,
                    analysis_vehicles=False,
                    analysis_only=False,
                    progress_callback=_on_video_progress,
                    cancel_check=_is_cancel_requested,
                )
                status = str(result.get("status", "processed"))
                indexed_frames = max(0, int(result.get("indexed_frames", 0)))
                indexed_windows = max(0, int(result.get("indexed_windows", 0)))
                processed_frames = max(0, int(result.get("processed_frames", 0)))
                estimated_total_frames = max(0, int(result.get("estimated_total_frames", 0)))
                if estimated_total_frames < processed_frames:
                    estimated_total_frames = processed_frames

                with lock:
                    current = jobs.get(normalized_case_id)
                    if not isinstance(current, dict):
                        return
                    current["completed"] = int(current.get("completed", 0)) + 1
                    if status == "skipped":
                        current["skipped"] = int(current.get("skipped", 0)) + 1
                    else:
                        current["processed"] = int(current.get("processed", 0)) + 1
                    current["indexed_frames"] = int(current.get("indexed_frames", 0)) + indexed_frames
                    current["indexed_windows"] = int(current.get("indexed_windows", 0)) + indexed_windows
                    current["current_video_processed_frames"] = processed_frames
                    current["current_video_total_frames"] = estimated_total_frames
                    if estimated_total_frames > 0:
                        current["current_video_progress_percent"] = 100.0
                        current["current_video_eta_seconds"] = 0.0
                    else:
                        current["current_video_progress_percent"] = 0.0
                        current["current_video_eta_seconds"] = None
                    results = current.setdefault("results", [])
                    if isinstance(results, list):
                        results.append(
                            {
                                "video_filename": str(result.get("video_filename") or filename),
                                "status": status,
                                "indexed_frames": indexed_frames,
                                "indexed_windows": indexed_windows,
                            }
                        )
                    current["updated_at"] = _utc_now_iso()
                pipeline_status = "completed"
                if status in {"skipped", "analysis_only", "not_requested"}:
                    pipeline_status = "skipped"
                elif status not in {"processed", "completed"}:
                    pipeline_status = "failed"
                await _pipeline_update_stage(
                    case_id=normalized_case_id,
                    filename=filename,
                    stage="base_index",
                    status=pipeline_status,
                    event=f"background_index_{pipeline_status}",
                    details={
                        "source": "background_index",
                        "status": status,
                        "indexed_frames": indexed_frames,
                        "indexed_windows": indexed_windows,
                        "processed_frames": processed_frames,
                        "estimated_total_frames": estimated_total_frames,
                    },
                )
                await _persist_index_job_snapshot(normalized_case_id)
            except _IndexCancellationRequested as exc:
                await _pipeline_update_stage(
                    case_id=normalized_case_id,
                    filename=filename,
                    stage="base_index",
                    status="interrupted",
                    event="background_index_cancelled",
                    error="Background indexing cancelled.",
                    details={
                        "source": "background_index",
                        "message": _truncate_error(str(exc)),
                    },
                )
                raise asyncio.CancelledError()
            except asyncio.CancelledError:
                await _pipeline_update_stage(
                    case_id=normalized_case_id,
                    filename=filename,
                    stage="base_index",
                    status="interrupted",
                    event="background_index_cancelled",
                    error="Background indexing cancelled.",
                    details={"source": "background_index"},
                )
                raise
            except Exception as exc:
                with lock:
                    current = jobs.get(normalized_case_id)
                    if not isinstance(current, dict):
                        return
                    current["completed"] = int(current.get("completed", 0)) + 1
                    current["failed"] = int(current.get("failed", 0)) + 1
                    errors = current.setdefault("errors", [])
                    if isinstance(errors, list):
                        errors.append(f"{filename}: {exc}")
                    current["current_video_eta_seconds"] = None
                    current["updated_at"] = _utc_now_iso()
                await _pipeline_update_stage(
                    case_id=normalized_case_id,
                    filename=filename,
                    stage="base_index",
                    status="failed",
                    event="background_index_failed",
                    error=_truncate_error(str(exc)),
                    details={"source": "background_index"},
                )
                await _persist_index_job_snapshot(normalized_case_id)
    except asyncio.CancelledError:
        with lock:
            current = jobs.get(normalized_case_id)
            if isinstance(current, dict):
                current["cancel_requested"] = True
                current["updated_at"] = _utc_now_iso()
                current_filename = str(current.get("current_filename") or "").strip()
            else:
                current_filename = ""
        if current_filename:
            await _pipeline_update_stage(
                case_id=normalized_case_id,
                filename=current_filename,
                stage="base_index",
                status="interrupted",
                event="background_index_interrupted",
                error="Background indexing cancelled.",
                details={"source": "background_index"},
            )
        await _persist_index_job_snapshot(normalized_case_id)
    except Exception as exc:
        with lock:
            current = jobs.get(normalized_case_id)
            if isinstance(current, dict):
                current["failed"] = int(current.get("failed", 0)) + 1
                errors = current.setdefault("errors", [])
                if isinstance(errors, list):
                    errors.append(f"Background indexing error: {exc}")
                current["updated_at"] = _utc_now_iso()
        await _persist_index_job_snapshot(normalized_case_id)
    finally:
        with lock:
            current = jobs.get(normalized_case_id)
            if isinstance(current, dict):
                cancelled = bool(current.get("cancel_requested", False))
                failed = int(current.get("failed", 0))
                processed = int(current.get("processed", 0))
                skipped = int(current.get("skipped", 0))
                if cancelled:
                    final_status = "cancelled"
                elif failed > 0 and processed == 0 and skipped == 0:
                    final_status = "failed"
                elif failed > 0:
                    final_status = "completed_with_errors"
                else:
                    final_status = "completed"
                now = _utc_now_iso()
                current["status"] = final_status
                current["running"] = False
                current["current_filename"] = ""
                current["current_video_eta_seconds"] = None
                current["current_video_started_ts"] = 0.0
                current["updated_at"] = now
                current["finished_at"] = now
            tasks.pop(normalized_case_id, None)
        await _persist_index_job_snapshot(normalized_case_id)


def _reset_store_files(paths: list[Path], label: str, reason: str) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink(missing_ok=True)
                print(f"[store-reset][{label}] removed={path} reason={reason}")
        except Exception as exc:
            print(f"[store-reset][{label}] failed_remove={path} error={exc}")


def _get_vector_store_for_case(case_id: str) -> tuple[CasePaths, VectorStore]:
    case_paths = _get_case_paths_or_raise(case_id)
    embedder: OpenCLIPEmbedder = app.state.embedder
    cache: dict[str, VectorStore] = app.state.vector_stores
    cache_lock: Lock = app.state.vector_stores_lock

    with cache_lock:
        store = cache.get(case_paths.case_id)
        if store is None:
            try:
                store = VectorStore(
                    index_path=case_paths.index_path,
                    metadata_path=case_paths.metadata_path,
                    expected_dimension=embedder.embedding_dim,
                )
            except RuntimeError as exc:
                if "Embedding dimension mismatch" not in str(exc):
                    raise
                _reset_store_files(
                    [case_paths.index_path, case_paths.metadata_path],
                    label=f"{case_paths.case_id}/semantic",
                    reason=str(exc),
                )
                store = VectorStore(
                    index_path=case_paths.index_path,
                    metadata_path=case_paths.metadata_path,
                    expected_dimension=embedder.embedding_dim,
                )
            cache[case_paths.case_id] = store

    return case_paths, store


def _get_temporal_store_for_case(case_id: str) -> tuple[CasePaths, TemporalWindowStore]:
    case_paths = _get_case_paths_or_raise(case_id)
    embedder: OpenCLIPEmbedder = app.state.embedder
    cache: dict[str, TemporalWindowStore] = app.state.temporal_stores
    cache_lock: Lock = app.state.temporal_stores_lock

    with cache_lock:
        store = cache.get(case_paths.case_id)
        if store is None:
            try:
                store = TemporalWindowStore(
                    index_path=case_paths.temporal_index_path,
                    metadata_path=case_paths.temporal_metadata_path,
                    expected_dimension=embedder.embedding_dim,
                )
            except RuntimeError as exc:
                if "dimension mismatch" not in str(exc).lower():
                    raise
                _reset_store_files(
                    [case_paths.temporal_index_path, case_paths.temporal_metadata_path],
                    label=f"{case_paths.case_id}/temporal",
                    reason=str(exc),
                )
                store = TemporalWindowStore(
                    index_path=case_paths.temporal_index_path,
                    metadata_path=case_paths.temporal_metadata_path,
                    expected_dimension=embedder.embedding_dim,
                )
            cache[case_paths.case_id] = store
    return case_paths, store


def _get_analysis_store_for_case(case_id: str) -> tuple[CasePaths, AnalysisCropStore]:
    case_paths = _get_case_paths_or_raise(case_id)
    embedder: OpenCLIPEmbedder = app.state.embedder
    cache: dict[str, AnalysisCropStore] = app.state.analysis_stores
    cache_lock: Lock = app.state.analysis_stores_lock

    with cache_lock:
        store = cache.get(case_paths.case_id)
        if store is None:
            try:
                store = AnalysisCropStore(
                    face_people_index_path=case_paths.face_people_index_path,
                    face_people_metadata_path=case_paths.face_people_metadata_path,
                    vehicles_index_path=case_paths.vehicles_index_path,
                    vehicles_metadata_path=case_paths.vehicles_metadata_path,
                    expected_dimension=embedder.embedding_dim,
                )
            except RuntimeError as exc:
                if "dimension mismatch" not in str(exc).lower():
                    raise
                _reset_store_files(
                    [
                        case_paths.face_people_index_path,
                        case_paths.face_people_metadata_path,
                        case_paths.vehicles_index_path,
                        case_paths.vehicles_metadata_path,
                    ],
                    label=f"{case_paths.case_id}/analysis",
                    reason=str(exc),
                )
                store = AnalysisCropStore(
                    face_people_index_path=case_paths.face_people_index_path,
                    face_people_metadata_path=case_paths.face_people_metadata_path,
                    vehicles_index_path=case_paths.vehicles_index_path,
                    vehicles_metadata_path=case_paths.vehicles_metadata_path,
                    expected_dimension=embedder.embedding_dim,
                )
            cache[case_paths.case_id] = store
    return case_paths, store


def _unique_video_path(
    target_dir: Path,
    filename: str,
    forced_suffix: str | None = None,
) -> tuple[str, Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_upload_filename(filename)
    stem = Path(safe_name).stem
    suffix = forced_suffix or Path(safe_name).suffix or ".mp4"
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    candidate_name = f"{stem}{suffix}"
    candidate_path = target_dir / candidate_name
    counter = 1

    while candidate_path.exists():
        candidate_name = f"{stem}_{counter}{suffix}"
        candidate_path = target_dir / candidate_name
        counter += 1

    return candidate_name, candidate_path


def _write_upload_file(upload: UploadFile, destination: Path) -> None:
    with destination.open("wb") as stream:
        shutil.copyfileobj(upload.file, stream)


def _truncate_error(message: str, limit: int = 300) -> str:
    clean = " ".join(str(message or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)] + "..."


def _unlink_with_retry(
    path: Path,
    attempts: int = 8,
    delay_seconds: float = 0.08,
    backoff_multiplier: float = 1.6,
    max_delay_seconds: float = 0.6,
) -> None:
    last_error: PermissionError | None = None
    for attempt_index in range(max(1, attempts)):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt_index < attempts - 1:
                delay = max(0.0, float(delay_seconds))
                if attempt_index > 0:
                    delay *= float(backoff_multiplier) ** attempt_index
                delay = min(delay, max(0.0, float(max_delay_seconds)))
                time.sleep(delay)

    if last_error is not None:
        raise last_error


def _describe_video_lock_context(case_id: str, filename: str) -> str:
    normalized_case_id = str(case_id or "").strip()
    normalized_filename = Path(str(filename or "")).name.strip()
    hints: list[str] = []

    index_jobs = getattr(app.state, "index_jobs", None)
    index_lock = getattr(app.state, "index_jobs_lock", None)
    if isinstance(index_jobs, dict) and isinstance(index_lock, Lock) and normalized_case_id:
        with index_lock:
            existing_job = index_jobs.get(normalized_case_id)
            if isinstance(existing_job, dict):
                status = str(existing_job.get("status") or "").strip().lower()
                running = bool(existing_job.get("running")) or status in {"queued", "running", "cancelling"}
                if running:
                    current_filename = str(existing_job.get("current_filename") or "").strip()
                    if current_filename and current_filename == normalized_filename:
                        hints.append(f"background indexing is processing '{current_filename}'")
                    elif current_filename:
                        hints.append(f"background indexing is running (current file: '{current_filename}')")
                    else:
                        hints.append("background indexing is running for this case")

    pipeline_store = getattr(app.state, "video_pipeline_store", None)
    if pipeline_store is not None and normalized_case_id and normalized_filename:
        snapshot: dict[str, Any] | None
        try:
            snapshot = pipeline_store.get_video_snapshot(normalized_case_id, normalized_filename)
        except Exception:
            snapshot = None

        if isinstance(snapshot, dict):
            overall_status = str(snapshot.get("overall_status") or "").strip().lower()
            current_stage = str(snapshot.get("current_stage") or "").strip()
            running_stage = ""
            stages = snapshot.get("stages")
            if isinstance(stages, dict):
                if current_stage:
                    current_payload = stages.get(current_stage)
                    current_status = (
                        str(current_payload.get("status") or "").strip().lower()
                        if isinstance(current_payload, dict)
                        else ""
                    )
                    if current_status == "running":
                        running_stage = current_stage
                if not running_stage:
                    for stage_name, stage_payload in stages.items():
                        if not isinstance(stage_payload, dict):
                            continue
                        stage_status = str(stage_payload.get("status") or "").strip().lower()
                        if stage_status == "running":
                            running_stage = str(stage_name).strip()
                            break
            if overall_status == "running":
                if running_stage:
                    hints.append(f"pipeline stage '{running_stage}' is still running")
                elif current_stage:
                    hints.append(f"pipeline stage '{current_stage}' may still be finalizing")
                else:
                    hints.append("video pipeline is still running for this video")

    if hints:
        return f"Possible lock owner: {'; '.join(hints)}."
    return (
        "Possible lock owner: browser playback tab, ffmpeg conversion, "
        "antivirus scanning, or another media app."
    )


def _float_from_env(name: str, default_value: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return float(default_value)
    try:
        return float(raw_value)
    except Exception:
        return float(default_value)


def _int_from_env(name: str, default_value: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return int(default_value)
    try:
        return int(raw_value)
    except Exception:
        return int(default_value)


def _media_url_for_case_path(path: Path) -> str:
    relative = path.relative_to(CASES_DIR).as_posix()
    return f"/media/cases/{quote(relative, safe='/')}"


def _safe_preview_stem(filename: str) -> str:
    raw_stem = Path(str(filename or "")).stem
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_stem).strip("_")
    return cleaned or "video"


def _preview_thumbnail_path(case_paths: CasePaths, filename: str) -> Path:
    safe_stem = _safe_preview_stem(filename)
    digest = hashlib.sha1(str(filename).encode("utf-8")).hexdigest()[:8]
    return case_paths.thumbnails_dir / "_previews" / f"{safe_stem}_{digest}.jpg"


def _triage_cache_video_dir(case_paths: CasePaths, filename: str) -> Path:
    safe_stem = _safe_preview_stem(filename)
    digest = hashlib.sha1(str(filename).encode("utf-8")).hexdigest()[:16]
    return case_paths.data_dir / "triage_cache" / f"{safe_stem}_{digest}"


def _triage_bucket_key(bucket_seconds: float) -> str:
    return f"{float(bucket_seconds):.3f}".replace(".", "_")


def _triage_cache_path(case_paths: CasePaths, filename: str, bucket_seconds: float) -> Path:
    return _triage_cache_video_dir(case_paths, filename) / f"bucket_{_triage_bucket_key(bucket_seconds)}.json"


def _triage_analysis_signature(face_people: dict, vehicles: dict) -> str:
    payload = {
        "face_people": face_people if isinstance(face_people, dict) else {},
        "vehicles": vehicles if isinstance(vehicles, dict) else {},
    }
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def _metadata_mtime_ns(path: Path) -> int:
    try:
        if path.exists():
            return int(path.stat().st_mtime_ns)
    except Exception:
        return 0
    return 0


def _load_triage_cache_sync(
    *,
    cache_path: Path,
    bucket_seconds: float,
    video_signature: str,
    analysis_signature: str,
    face_people_metadata_mtime_ns: int,
    vehicles_metadata_mtime_ns: int,
) -> dict | None:
    if not cache_path.exists() or not cache_path.is_file():
        return None

    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(cached, dict):
        return None

    if int(cached.get("cache_version", 0)) != TRIAGE_CACHE_VERSION:
        return None
    if str(cached.get("video_signature", "")) != str(video_signature):
        return None
    if str(cached.get("analysis_signature", "")) != str(analysis_signature):
        return None
    if int(cached.get("face_people_metadata_mtime_ns", 0)) != int(face_people_metadata_mtime_ns):
        return None
    if int(cached.get("vehicles_metadata_mtime_ns", 0)) != int(vehicles_metadata_mtime_ns):
        return None
    try:
        cached_bucket_seconds = float(cached.get("bucket_seconds", -1.0))
    except Exception:
        return None
    if abs(cached_bucket_seconds - float(bucket_seconds)) > 1e-6:
        return None

    payload = cached.get("payload")
    if not isinstance(payload, dict):
        return None
    return dict(payload)


def _save_triage_cache_sync(
    *,
    cache_path: Path,
    bucket_seconds: float,
    video_signature: str,
    analysis_signature: str,
    face_people_metadata_mtime_ns: int,
    vehicles_metadata_mtime_ns: int,
    payload: dict,
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = {
        "cache_version": TRIAGE_CACHE_VERSION,
        "bucket_seconds": float(bucket_seconds),
        "video_signature": str(video_signature),
        "analysis_signature": str(analysis_signature),
        "face_people_metadata_mtime_ns": int(face_people_metadata_mtime_ns),
        "vehicles_metadata_mtime_ns": int(vehicles_metadata_mtime_ns),
        "payload": payload,
        "updated_at": _utc_now_iso(),
    }
    cache_path.write_text(
        json.dumps(wrapped, ensure_ascii=False),
        encoding="utf-8",
    )


def _clear_triage_cache_for_video(case_paths: CasePaths, filename: str) -> None:
    video_cache_dir = _triage_cache_video_dir(case_paths, filename)
    if video_cache_dir.exists() and video_cache_dir.is_dir():
        shutil.rmtree(video_cache_dir, ignore_errors=True)


def _semantic_result_unique_key(item: dict) -> tuple[str, float, str]:
    video_filename = str(item.get("video_filename") or "")
    timestamp = float(item.get("timestamp_seconds") or 0.0)
    thumbnail_path = str(item.get("thumbnail_path") or "")
    return video_filename, round(timestamp, 3), thumbnail_path


def _apply_semantic_post_filters(
    raw_results: list[dict],
    *,
    top_k: int,
    min_score: float,
    diversity_seconds: float,
) -> list[dict]:
    if top_k <= 0 or not raw_results:
        return []

    sorted_results = sorted(
        raw_results,
        key=lambda item: float(item.get("similarity_score", -1.0)),
        reverse=True,
    )
    thresholded = [
        item
        for item in sorted_results
        if float(item.get("similarity_score", -1.0)) >= float(min_score)
    ]
    candidates = thresholded if thresholded else sorted_results

    if diversity_seconds <= 0:
        return candidates[:top_k]

    selected: list[dict] = []
    used_keys: set[tuple[str, float, str]] = set()
    per_video_buckets: dict[str, set[int]] = {}

    for item in candidates:
        key = _semantic_result_unique_key(item)
        if key in used_keys:
            continue

        video_filename = key[0]
        timestamp = key[1]
        if video_filename:
            bucket = int(max(0.0, float(timestamp)) // float(diversity_seconds))
            seen_buckets = per_video_buckets.setdefault(video_filename, set())
            if bucket in seen_buckets:
                continue
            seen_buckets.add(bucket)

        used_keys.add(key)
        selected.append(item)
        if len(selected) >= top_k:
            return selected

    if len(selected) < top_k:
        for item in candidates:
            key = _semantic_result_unique_key(item)
            if key in used_keys:
                continue
            used_keys.add(key)
            selected.append(item)
            if len(selected) >= top_k:
                break

    return selected[:top_k]


def _build_temporal_window_records_and_embeddings(
    *,
    frame_records: list[dict],
    frame_embeddings: np.ndarray,
    window_seconds: float,
    stride_seconds: float,
) -> tuple[list[dict], np.ndarray]:
    if not frame_records:
        return [], np.empty((0, 0), dtype=np.float32)

    embeddings = np.asarray(frame_embeddings, dtype=np.float32)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(frame_records):
        return [], np.empty((0, 0), dtype=np.float32)

    safe_window = max(0.5, float(window_seconds))
    safe_stride = max(0.25, float(stride_seconds))
    if safe_stride > safe_window:
        safe_stride = safe_window

    timestamps = np.asarray(
        [float(item.get("timestamp_seconds", 0.0)) for item in frame_records],
        dtype=np.float32,
    )
    if timestamps.size == 0:
        return [], np.empty((0, embeddings.shape[1]), dtype=np.float32)

    last_ts = float(max(0.0, timestamps[-1]))
    max_start = max(0.0, last_ts - safe_window)
    start_seconds = 0.0
    records: list[dict] = []
    vectors: list[np.ndarray] = []
    seen_keys: set[tuple[float, float, float]] = set()

    while start_seconds <= max_start + 1e-6:
        end_seconds = start_seconds + safe_window
        indices = np.where((timestamps >= start_seconds) & (timestamps < end_seconds))[0]
        if indices.size > 0:
            start_idx = int(indices[0])
            end_idx = int(indices[-1])
            center_idx = int(indices[indices.size // 2])
            center_ts = float(frame_records[center_idx]["timestamp_seconds"])
            window_key = (round(start_seconds, 3), round(end_seconds, 3), round(center_ts, 3))
            if window_key not in seen_keys:
                seen_keys.add(window_key)
                window_vec = embeddings[start_idx : end_idx + 1].mean(axis=0).astype(np.float32)
                norm = float(np.linalg.norm(window_vec))
                if norm > 0:
                    window_vec = (window_vec / norm).astype(np.float32)
                records.append(
                    {
                        "timestamp_seconds": center_ts,
                        "start_seconds": float(start_seconds),
                        "end_seconds": float(end_seconds),
                        "thumbnail_path": str(frame_records[center_idx]["thumbnail_path"]),
                    }
                )
                vectors.append(window_vec)
        start_seconds += safe_stride

    if not records:
        # Fallback for very short videos: one single temporal window.
        center_idx = len(frame_records) // 2
        center_ts = float(frame_records[center_idx]["timestamp_seconds"])
        merged = embeddings.mean(axis=0).astype(np.float32)
        norm = float(np.linalg.norm(merged))
        if norm > 0:
            merged = (merged / norm).astype(np.float32)
        records = [
            {
                "timestamp_seconds": center_ts,
                "start_seconds": 0.0,
                "end_seconds": float(max(safe_window, last_ts)),
                "thumbnail_path": str(frame_records[center_idx]["thumbnail_path"]),
            }
        ]
        vectors = [merged]

    return records, np.vstack(vectors).astype(np.float32)


def _clip_box_to_frame(
    box: tuple[int, int, int, int],
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = box
    x1 = max(0, min(frame_width - 1, int(x1)))
    y1 = max(0, min(frame_height - 1, int(y1)))
    x2 = max(0, min(frame_width, int(x2)))
    y2 = max(0, min(frame_height, int(y2)))
    if x2 <= x1 or y2 <= y1:
        return None
    if (x2 - x1) < 4 or (y2 - y1) < 4:
        return None
    return x1, y1, x2, y2


def _save_detection_crop(
    *,
    frame_rgb: np.ndarray,
    box: tuple[int, int, int, int],
    output_dir: Path,
    kind: str,
    timestamp_seconds: float,
    index_in_frame: int,
) -> Path | None:
    frame_height, frame_width = frame_rgb.shape[:2]
    clipped = _clip_box_to_frame(box, frame_width=frame_width, frame_height=frame_height)
    if clipped is None:
        return None

    x1, y1, x2, y2 = clipped
    crop = frame_rgb[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    millis = int(round(float(timestamp_seconds) * 1000))
    filename = f"{kind}_{millis:09d}_{int(index_in_frame):03d}.jpg"
    crop_path = output_dir / filename
    crop_bgr = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(crop_path), crop_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return crop_path


def _resolve_video_path_for_processing(
    case_paths: CasePaths,
    filename: str,
) -> tuple[str, Path]:
    requested_name = Path(filename).name
    requested_path = case_paths.videos_dir / requested_name
    mp4_path = requested_path.with_suffix(".mp4")

    if mp4_path.exists() and mp4_path.is_file():
        return mp4_path.name, mp4_path

    if requested_path.suffix.lower() == ".mp4" and not requested_path.exists():
        stem = requested_path.stem
        for ext in sorted(VIDEO_EXTENSIONS):
            if ext == ".mp4":
                continue
            candidate = case_paths.videos_dir / f"{stem}{ext}"
            if candidate.exists() and candidate.is_file():
                return candidate.name, candidate

    return requested_name, requested_path


def _analysis_summary_from_record(record: dict | None) -> dict:
    payload = record if isinstance(record, dict) else {}
    face_data = payload.get("face_people") if isinstance(payload.get("face_people"), dict) else {}
    vehicle_data = payload.get("vehicles") if isinstance(payload.get("vehicles"), dict) else {}
    def _safe_optional_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    return {
        "face_people": {
            "processed": bool(face_data.get("processed")),
            "face_count": int(face_data.get("face_count", 0)),
            "people_count": int(face_data.get("people_count", 0)),
            "hit_frames": int(face_data.get("hit_frames", 0)),
            "first_hit_seconds": _safe_optional_float(face_data.get("first_hit_seconds")),
        },
        "vehicles": {
            "processed": bool(vehicle_data.get("processed")),
            "vehicle_count": int(vehicle_data.get("vehicle_count", 0)),
            "hit_frames": int(vehicle_data.get("hit_frames", 0)),
            "first_hit_seconds": _safe_optional_float(vehicle_data.get("first_hit_seconds")),
        },
        "processed_frames": int(payload.get("processed_frames", 0)),
        "detector": str(payload.get("detector", "")),
    }


def _run_optional_analysis_sync(
    *,
    case_paths: CasePaths,
    vector_store: VectorStore,
    resolved_filename: str,
    video_path: Path,
    signature: str,
    frame_interval_seconds: float,
    batch_size: int,
    selection: AnalysisSelection,
    force: bool,
) -> dict:
    requested = selection.to_dict()
    if not selection.any_selected():
        existing_record = vector_store.get_video_analysis(signature, frame_interval_seconds)
        return {
            "requested": requested,
            "pending": {"face_people": False, "vehicles": False},
            "ran": False,
            "status": "not_requested",
            "summary": _analysis_summary_from_record(existing_record),
        }

    _, analysis_store = _get_analysis_store_for_case(case_paths.case_id)
    existing_status = vector_store.get_video_analysis_status(
        signature,
        frame_interval_seconds,
    )
    has_face_crops = analysis_store.has_video_entries(
        category=AnalysisCropStore.FACE_PEOPLE,
        video_filename=resolved_filename,
    )
    has_vehicle_crops = analysis_store.has_video_entries(
        category=AnalysisCropStore.VEHICLES,
        video_filename=resolved_filename,
    )
    pending = {
        "face_people": bool(requested["face_people"]) and (
            force or not existing_status["face_people"] or not has_face_crops
        ),
        "vehicles": bool(requested["vehicles"]) and (
            force or not existing_status["vehicles"] or not has_vehicle_crops
        ),
    }

    if not pending["face_people"] and not pending["vehicles"]:
        existing_record = vector_store.get_video_analysis(signature, frame_interval_seconds)
        return {
            "requested": requested,
            "pending": pending,
            "ran": False,
            "status": "skipped",
            "reason": "selected analysis already completed",
            "summary": _analysis_summary_from_record(existing_record),
        }

    analyzer: VideoAnalyzer = app.state.analyzer
    if analyzer is None or not analyzer.available:
        existing_record = vector_store.get_video_analysis(signature, frame_interval_seconds)
        return {
            "requested": requested,
            "pending": pending,
            "ran": False,
            "status": "unavailable",
            "reason": analyzer.detector_label() if analyzer else "Analyzer unavailable",
            "summary": _analysis_summary_from_record(existing_record),
        }

    pending_selection = AnalysisSelection(
        face_people=pending["face_people"],
        vehicles=pending["vehicles"],
    )

    detections_root = case_paths.thumbnails_dir / "detections" / Path(resolved_filename).stem
    if pending["face_people"]:
        shutil.rmtree(detections_root / "face_people", ignore_errors=True)
    if pending["vehicles"]:
        shutil.rmtree(detections_root / "vehicles", ignore_errors=True)

    face_people_records: list[dict] = []
    face_people_images: list[Image.Image] = []
    vehicle_records: list[dict] = []
    vehicle_images: list[Image.Image] = []

    processed_frames = 0
    face_count = 0
    people_count = 0
    vehicle_count = 0
    face_people_hit_frames = 0
    vehicle_hit_frames = 0
    face_people_first_hit_seconds: float | None = None
    vehicle_first_hit_seconds: float | None = None

    def _append_detection(
        *,
        frame_rgb: np.ndarray,
        timestamp_seconds: float,
        box: tuple[int, int, int, int],
        output_dir: Path,
        kind: str,
        index_in_frame: int,
        records: list[dict],
        images: list[Image.Image],
    ) -> None:
        clipped = _clip_box_to_frame(
            box,
            frame_width=frame_rgb.shape[1],
            frame_height=frame_rgb.shape[0],
        )
        if clipped is None:
            return
        x1, y1, x2, y2 = clipped
        crop_rgb = frame_rgb[y1:y2, x1:x2]
        if crop_rgb.size == 0:
            return
        crop_path = _save_detection_crop(
            frame_rgb=frame_rgb,
            box=clipped,
            output_dir=output_dir,
            kind=kind,
            timestamp_seconds=timestamp_seconds,
            index_in_frame=index_in_frame,
        )
        if crop_path is None:
            return
        records.append(
            {
                "timestamp_seconds": float(timestamp_seconds),
                "crop_path": _media_url_for_case_path(crop_path),
                "kind": kind,
            }
        )
        images.append(Image.fromarray(crop_rgb))

    try:
        for frame in iter_video_frames(video_path, interval_seconds=frame_interval_seconds):
            processed_frames += 1
            detections = analyzer.detect_frame(frame.frame_rgb, pending_selection)

            if pending["face_people"]:
                face_boxes = detections["faces"]
                people_boxes = detections["people"]
                face_count += len(face_boxes)
                people_count += len(people_boxes)
                if face_boxes or people_boxes:
                    face_people_hit_frames += 1
                    if face_people_first_hit_seconds is None:
                        face_people_first_hit_seconds = float(frame.timestamp_seconds)

                for idx, box in enumerate(face_boxes):
                    _append_detection(
                        frame_rgb=frame.frame_rgb,
                        timestamp_seconds=frame.timestamp_seconds,
                        box=box,
                        output_dir=detections_root / "face_people" / "faces",
                        kind="face",
                        index_in_frame=idx,
                        records=face_people_records,
                        images=face_people_images,
                    )
                for idx, box in enumerate(people_boxes):
                    _append_detection(
                        frame_rgb=frame.frame_rgb,
                        timestamp_seconds=frame.timestamp_seconds,
                        box=box,
                        output_dir=detections_root / "face_people" / "people",
                        kind="people",
                        index_in_frame=idx,
                        records=face_people_records,
                        images=face_people_images,
                    )

            if pending["vehicles"]:
                vehicle_boxes = detections["vehicles"]
                vehicle_count += len(vehicle_boxes)
                if vehicle_boxes:
                    vehicle_hit_frames += 1
                    if vehicle_first_hit_seconds is None:
                        vehicle_first_hit_seconds = float(frame.timestamp_seconds)
                for idx, box in enumerate(vehicle_boxes):
                    _append_detection(
                        frame_rgb=frame.frame_rgb,
                        timestamp_seconds=frame.timestamp_seconds,
                        box=box,
                        output_dir=detections_root / "vehicles",
                        kind="vehicle",
                        index_in_frame=idx,
                        records=vehicle_records,
                        images=vehicle_images,
                    )
    except Exception as exc:
        existing_record = vector_store.get_video_analysis(signature, frame_interval_seconds)
        return {
            "requested": requested,
            "pending": pending,
            "ran": False,
            "status": "failed",
            "reason": _truncate_error(str(exc)),
            "summary": _analysis_summary_from_record(existing_record),
        }

    embedder: OpenCLIPEmbedder = app.state.embedder
    if pending["face_people"]:
        if face_people_images:
            face_people_embeddings = embedder.encode_images(
                face_people_images,
                batch_size=batch_size,
            )
        else:
            face_people_embeddings = np.empty(
                (0, embedder.embedding_dim),
                dtype=np.float32,
            )
        analysis_store.upsert_detections(
            category=AnalysisCropStore.FACE_PEOPLE,
            video_filename=resolved_filename,
            records=face_people_records,
            embeddings=face_people_embeddings,
            force=force or not existing_status["face_people"],
        )

    if pending["vehicles"]:
        if vehicle_images:
            vehicle_embeddings = embedder.encode_images(
                vehicle_images,
                batch_size=batch_size,
            )
        else:
            vehicle_embeddings = np.empty((0, embedder.embedding_dim), dtype=np.float32)
        analysis_store.upsert_detections(
            category=AnalysisCropStore.VEHICLES,
            video_filename=resolved_filename,
            records=vehicle_records,
            embeddings=vehicle_embeddings,
            force=force or not existing_status["vehicles"],
        )

    stored = vector_store.upsert_video_analysis(
        signature=signature,
        analysis_interval_seconds=frame_interval_seconds,
        video_filename=resolved_filename,
        selected=pending,
        frame_count=int(processed_frames),
        face_count=int(face_count),
        people_count=int(people_count),
        vehicle_count=int(vehicle_count),
        face_people_hit_frames=int(face_people_hit_frames),
        vehicle_hit_frames=int(vehicle_hit_frames),
        face_people_first_hit_seconds=face_people_first_hit_seconds,
        vehicle_first_hit_seconds=vehicle_first_hit_seconds,
        detector=analyzer.detector_label(),
        force=force,
    )

    print(
        f"[analysis][{case_paths.case_id}] file={resolved_filename} "
        f"pending={pending} processed_frames={processed_frames} "
        f"face_crops={len(face_people_records)} vehicle_crops={len(vehicle_records)}"
    )

    return {
        "requested": requested,
        "pending": pending,
        "ran": True,
        "status": "processed",
        "summary": _analysis_summary_from_record(stored),
    }


def _estimate_sampled_frame_count(video_path: Path, interval_seconds: float) -> int:
    safe_interval = max(0.001, float(interval_seconds))
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return 0

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps <= 0 or frame_count <= 0:
            return 0
        duration_seconds = frame_count / fps
        if duration_seconds <= 0:
            return 0
        estimated = int(duration_seconds / safe_interval) + 1
        return max(1, estimated)
    except Exception:
        return 0
    finally:
        capture.release()


class _IndexCancellationRequested(Exception):
    pass


def _process_video_sync(
    *,
    case_id: str,
    filename: str,
    frame_interval_seconds: float,
    batch_size: int,
    force: bool,
    analysis_face_people: bool,
    analysis_vehicles: bool,
    analysis_only: bool,
    progress_callback=None,
    cancel_check=None,
) -> dict:
    case_paths, vector_store = _get_vector_store_for_case(case_id)
    _, temporal_store = _get_temporal_store_for_case(case_id)
    resolved_filename, video_path = _resolve_video_path_for_processing(case_paths, filename)

    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(filename)
    if not _is_supported_video(video_path.name):
        raise ValueError(
            "Unsupported video format. Allowed extensions: "
            + ", ".join(sorted(VIDEO_EXTENSIONS))
        )

    signature = compute_video_signature(video_path)
    engine_info = _embedding_engine_info()
    temporal_window_seconds = max(0.5, _float_from_env("SEMANTIC_WINDOW_SECONDS", 8.0))
    temporal_stride_seconds = max(0.25, _float_from_env("SEMANTIC_WINDOW_STRIDE_SECONDS", 2.0))
    if temporal_stride_seconds > temporal_window_seconds:
        temporal_stride_seconds = temporal_window_seconds

    print(
        f"[process][{case_paths.case_id}] file={resolved_filename} "
        f"model={engine_info['model_name']} pretrained={engine_info['pretrained']} "
        f"device={engine_info['device']} analysis_only={analysis_only}"
    )

    base_status = "analysis_only"
    base_reason = ""
    indexed_frames = vector_store.get_indexed_frame_count(
        signature,
        frame_interval_seconds,
    )
    indexed_windows = temporal_store.get_indexed_window_count(
        signature,
        frame_interval_seconds,
        temporal_window_seconds,
        temporal_stride_seconds,
    )
    processed_frames = 0
    estimated_total_frames = 0
    temporal_status = "not_requested" if analysis_only else "skipped"
    temporal_reason = "analysis_only mode" if analysis_only else "already indexed for this interval"

    if not analysis_only:
        frame_indexed = vector_store.is_video_indexed(signature, frame_interval_seconds)
        temporal_indexed = temporal_store.is_video_indexed(
            signature,
            frame_interval_seconds,
            temporal_window_seconds,
            temporal_stride_seconds,
        )

        if frame_indexed and temporal_indexed and not force:
            base_status = "skipped"
            base_reason = "video already indexed for frame and temporal indexes"
            temporal_status = "skipped"
            temporal_reason = "video already indexed for temporal windows"
            estimated_total_frames = max(0, int(indexed_frames))
            if progress_callback is not None and estimated_total_frames > 0:
                try:
                    progress_callback(estimated_total_frames, estimated_total_frames)
                except Exception:
                    pass
        else:
            if cancel_check is not None and bool(cancel_check()):
                raise _IndexCancellationRequested(
                    f"Background indexing cancelled before frame extraction: {resolved_filename}"
                )
            thumbnail_dir = case_paths.thumbnails_dir / Path(resolved_filename).stem
            if force and thumbnail_dir.exists():
                shutil.rmtree(thumbnail_dir)
            thumbnail_dir.mkdir(parents=True, exist_ok=True)

            records: list[dict] = []
            embeddings_batches: list[np.ndarray] = []
            pending_images: list[Image.Image] = []
            total_frames = 0
            estimated_total_frames = _estimate_sampled_frame_count(video_path, frame_interval_seconds)
            if progress_callback is not None:
                try:
                    progress_callback(0, estimated_total_frames)
                except Exception:
                    pass

            for frame in iter_video_frames(video_path, interval_seconds=frame_interval_seconds):
                if cancel_check is not None and bool(cancel_check()):
                    raise _IndexCancellationRequested(
                        f"Background indexing cancelled while processing frames: {resolved_filename}"
                    )
                thumb_path = save_thumbnail(
                    frame_rgb=frame.frame_rgb,
                    output_dir=thumbnail_dir,
                    video_stem=Path(resolved_filename).stem,
                    timestamp_seconds=frame.timestamp_seconds,
                )
                thumb_url = _media_url_for_case_path(thumb_path)
                records.append(
                    {
                        "timestamp_seconds": frame.timestamp_seconds,
                        "thumbnail_path": thumb_url,
                    }
                )
                pending_images.append(Image.fromarray(frame.frame_rgb))
                total_frames += 1
                if progress_callback is not None:
                    try:
                        progress_callback(total_frames, estimated_total_frames)
                    except Exception:
                        pass

                if len(pending_images) >= batch_size:
                    if cancel_check is not None and bool(cancel_check()):
                        raise _IndexCancellationRequested(
                            f"Background indexing cancelled before embedding batch: {resolved_filename}"
                        )
                    embeddings_batches.append(
                        app.state.embedder.encode_images(pending_images, batch_size=batch_size)
                    )
                    pending_images.clear()

            if pending_images:
                if cancel_check is not None and bool(cancel_check()):
                    raise _IndexCancellationRequested(
                        f"Background indexing cancelled before final embedding batch: {resolved_filename}"
                    )
                embeddings_batches.append(
                    app.state.embedder.encode_images(pending_images, batch_size=batch_size)
                )

            if embeddings_batches:
                video_embeddings = np.vstack(embeddings_batches).astype(np.float32)
            else:
                video_embeddings = np.empty((0, app.state.embedder.embedding_dim), dtype=np.float32)

            if estimated_total_frames < total_frames:
                estimated_total_frames = total_frames
            if progress_callback is not None:
                try:
                    progress_callback(total_frames, estimated_total_frames)
                except Exception:
                    pass

            frame_upsert_result = vector_store.upsert_video_embeddings(
                signature=signature,
                frame_interval_seconds=frame_interval_seconds,
                video_filename=resolved_filename,
                records=records,
                embeddings=video_embeddings,
                force=force,
            )
            temporal_records, temporal_embeddings = _build_temporal_window_records_and_embeddings(
                frame_records=records,
                frame_embeddings=video_embeddings,
                window_seconds=temporal_window_seconds,
                stride_seconds=temporal_stride_seconds,
            )
            temporal_upsert_result = temporal_store.upsert_video_windows(
                signature=signature,
                frame_interval_seconds=frame_interval_seconds,
                window_seconds=temporal_window_seconds,
                stride_seconds=temporal_stride_seconds,
                video_filename=resolved_filename,
                records=temporal_records,
                embeddings=temporal_embeddings,
                force=force,
            )

            base_status = str(frame_upsert_result.get("status", "processed"))
            indexed_frames = int(frame_upsert_result.get("indexed_frames", 0))
            temporal_status = str(temporal_upsert_result.get("status", "processed"))
            indexed_windows = int(temporal_upsert_result.get("indexed_windows", 0))
            processed_frames = total_frames
            if base_status != "skipped":
                base_reason = ""
            temporal_reason = ""

    analysis_payload = _run_optional_analysis_sync(
        case_paths=case_paths,
        vector_store=vector_store,
        resolved_filename=resolved_filename,
        video_path=video_path,
        signature=signature,
        frame_interval_seconds=frame_interval_seconds,
        batch_size=batch_size,
        selection=AnalysisSelection(
            face_people=analysis_face_people,
            vehicles=analysis_vehicles,
        ),
        force=force,
    )

    response = {
        "status": base_status,
        "reason": base_reason,
        "case_id": case_paths.case_id,
        "video_filename": resolved_filename,
        "indexed_frames": indexed_frames,
        "indexed_windows": indexed_windows,
        "processed_frames": processed_frames,
        "estimated_total_frames": estimated_total_frames,
        "frame_interval_seconds": frame_interval_seconds,
        "temporal_window_seconds": temporal_window_seconds,
        "temporal_stride_seconds": temporal_stride_seconds,
        "temporal_index": {
            "status": temporal_status,
            "reason": temporal_reason,
            "indexed_windows": indexed_windows,
        },
        "embedding_engine": engine_info,
        "analysis": analysis_payload,
    }
    if not base_reason:
        response.pop("reason", None)
    if not temporal_reason:
        response["temporal_index"].pop("reason", None)
    return response


def _delete_video_sync(case_id: str, filename: str) -> dict:
    case_paths, vector_store = _get_vector_store_for_case(case_id)
    _, temporal_store = _get_temporal_store_for_case(case_id)
    _, analysis_store = _get_analysis_store_for_case(case_id)
    safe_filename = Path(str(filename or "")).name.strip()
    if not safe_filename:
        raise ValueError("filename is required")

    video_path = case_paths.videos_dir / safe_filename
    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(safe_filename)

    try:
        _unlink_with_retry(video_path)
    except PermissionError as exc:
        lock_context = _describe_video_lock_context(case_paths.case_id, safe_filename)
        os_error = _truncate_error(str(exc), limit=180)
        raise PermissionError(
            "Video file is currently in use. "
            f"{lock_context} "
            "Close anything playing or editing this file, then retry. "
            f"Path: {video_path}. OS error: {os_error}"
        ) from exc

    vector_result = vector_store.delete_video_embeddings(safe_filename)
    temporal_result = temporal_store.delete_video_windows(safe_filename)
    crop_result = analysis_store.delete_video(safe_filename)

    thumbnail_dir = case_paths.thumbnails_dir / Path(safe_filename).stem
    if thumbnail_dir.exists():
        shutil.rmtree(thumbnail_dir, ignore_errors=True)
    detections_dir = case_paths.thumbnails_dir / "detections" / Path(safe_filename).stem
    if detections_dir.exists():
        shutil.rmtree(detections_dir, ignore_errors=True)
    preview_path = _preview_thumbnail_path(case_paths, safe_filename)
    preview_path.unlink(missing_ok=True)
    _clear_triage_cache_for_video(case_paths, safe_filename)

    return {
        "case_id": case_paths.case_id,
        "filename": safe_filename,
        "deleted": True,
        "removed_vectors": int(vector_result.get("removed_vectors", 0)),
        "removed_records": int(vector_result.get("removed_records", 0)),
        "removed_analysis_records": int(vector_result.get("removed_analysis_records", 0)),
        "removed_temporal_vectors": int(temporal_result.get("removed_vectors", 0)),
        "removed_temporal_records": int(temporal_result.get("removed_records", 0)),
        "removed_face_people_crops": int(crop_result.get("removed_face_people", 0)),
        "removed_vehicle_crops": int(crop_result.get("removed_vehicles", 0)),
    }

_process_control_service = ProcessControlService(
    app=app,
    utc_now_iso=_utc_now_iso,
    index_job_snapshot=_index_job_snapshot,
)
app.state.process_control_service = _process_control_service

app.include_router(
    build_cases_router(
        create_case_sync=_create_case_sync,
        list_cases_sync=_list_cases_sync,
        rename_case_sync=_rename_case_sync,
        delete_case_sync=_delete_case_sync,
        normalize_case_id=_normalize_case_id,
    )
)
app.include_router(
    build_embedding_settings_router(
        read_saved_settings_sync=_read_saved_embedding_settings_sync,
        write_saved_settings_sync=_write_saved_embedding_settings_sync,
        build_settings_response_sync=_build_embedding_settings_response_sync,
    )
)
_media_service = MediaService(
    app=app,
    video_extensions=VIDEO_EXTENSIONS,
    convert_to_mp4=convert_to_mp4,
    generate_preview_thumbnail=generate_preview_thumbnail,
    resolve_case_id_or_default=_resolve_case_id_or_default,
    get_case_paths_or_raise=_get_case_paths_or_raise,
    is_supported_video=_is_supported_video,
    unique_video_path=_unique_video_path,
    write_upload_file=_write_upload_file,
    truncate_error=_truncate_error,
    preview_thumbnail_path=_preview_thumbnail_path,
    media_url_for_case_path=_media_url_for_case_path,
    get_vector_store_for_case=_get_vector_store_for_case,
    get_temporal_store_for_case=_get_temporal_store_for_case,
    delete_video_sync=_delete_video_sync,
    process_video_sync=_process_video_sync,
    resolve_index_filenames=_resolve_index_filenames,
    find_running_index_case_id_locked=_find_running_index_case_id_locked,
    new_index_job_record=_new_index_job_record,
    run_index_job_async=_run_index_job_async,
    index_job_snapshot=_index_job_snapshot,
)
app.include_router(build_media_router(media_service=_media_service))

app.include_router(
    build_process_control_router(process_control_service=_process_control_service)
)


def _hydrate_crop_item(case_paths: CasePaths, item: dict) -> dict:
    video_filename = str(item.get("video_filename") or "")
    output = {
        "video_filename": video_filename,
        "timestamp_seconds": float(item.get("timestamp_seconds", 0.0)),
        "crop_url": str(item.get("crop_path") or ""),
        "kind": str(item.get("kind") or ""),
        "video_url": _media_url_for_case_path(case_paths.videos_dir / video_filename),
    }
    if "similarity_score" in item:
        output["similarity_score"] = float(item.get("similarity_score", 0.0))
    return output


def _build_video_triage_sync(
    *,
    case_id: str,
    filename: str,
    bucket_seconds: float,
    force: bool = False,
) -> dict:
    case_paths, vector_store = _get_vector_store_for_case(case_id)
    resolved_filename, video_path = _resolve_video_path_for_processing(
        case_paths,
        filename,
    )
    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(resolved_filename)
    if not _is_supported_video(video_path.name):
        raise ValueError(
            "Unsupported video format. Allowed extensions: "
            + ", ".join(sorted(VIDEO_EXTENSIONS))
        )

    analysis_summary = vector_store.analysis_summary_by_filename().get(
        resolved_filename,
        {
            "face_people": {"processed": False},
            "vehicles": {"processed": False},
        },
    )
    face_people = (
        analysis_summary.get("face_people")
        if isinstance(analysis_summary.get("face_people"), dict)
        else {}
    )
    vehicles = (
        analysis_summary.get("vehicles")
        if isinstance(analysis_summary.get("vehicles"), dict)
        else {}
    )

    safe_bucket_seconds = max(0.5, float(bucket_seconds))
    video_signature = compute_video_signature(video_path)
    face_people_mtime_ns = _metadata_mtime_ns(case_paths.face_people_metadata_path)
    vehicles_mtime_ns = _metadata_mtime_ns(case_paths.vehicles_metadata_path)
    analysis_signature = _triage_analysis_signature(face_people, vehicles)
    cache_path = _triage_cache_path(
        case_paths,
        resolved_filename,
        safe_bucket_seconds,
    )

    if not force:
        cached_payload = _load_triage_cache_sync(
            cache_path=cache_path,
            bucket_seconds=safe_bucket_seconds,
            video_signature=video_signature,
            analysis_signature=analysis_signature,
            face_people_metadata_mtime_ns=face_people_mtime_ns,
            vehicles_metadata_mtime_ns=vehicles_mtime_ns,
        )
        if isinstance(cached_payload, dict):
            _pipeline_update_stage_sync(
                case_id=case_paths.case_id,
                filename=resolved_filename,
                stage="triage",
                status="skipped",
                event="triage_cache_hit",
                details={
                    "bucket_seconds": safe_bucket_seconds,
                    "cache_status": "hit",
                    "force": force,
                },
            )
            cached_payload["case_id"] = case_paths.case_id
            cached_payload["video_url"] = _media_url_for_case_path(
                case_paths.videos_dir / resolved_filename
            )
            cached_payload["cache_status"] = "hit"
            return cached_payload

    _pipeline_update_stage_sync(
        case_id=case_paths.case_id,
        filename=resolved_filename,
        stage="triage",
        status="running",
        increment_attempt=True,
        event="triage_started",
        details={
            "bucket_seconds": safe_bucket_seconds,
            "cache_status": "miss",
            "force": force,
        },
    )

    try:
        payload = build_video_triage_payload(
            video_path=video_path,
            video_filename=resolved_filename,
            bucket_seconds=safe_bucket_seconds,
            face_people_metadata_path=case_paths.face_people_metadata_path,
            vehicles_metadata_path=case_paths.vehicles_metadata_path,
            face_people_processed=bool(face_people.get("processed")),
            vehicles_processed=bool(vehicles.get("processed")),
        )
    except Exception as exc:
        _pipeline_update_stage_sync(
            case_id=case_paths.case_id,
            filename=resolved_filename,
            stage="triage",
            status="failed",
            event="triage_failed",
            error=_truncate_error(str(exc)),
            details={"bucket_seconds": safe_bucket_seconds, "force": force},
        )
        raise

    try:
        _save_triage_cache_sync(
            cache_path=cache_path,
            bucket_seconds=safe_bucket_seconds,
            video_signature=video_signature,
            analysis_signature=analysis_signature,
            face_people_metadata_mtime_ns=face_people_mtime_ns,
            vehicles_metadata_mtime_ns=vehicles_mtime_ns,
            payload=payload,
        )
    except Exception as exc:
        print(
            f"[triage-cache][{case_paths.case_id}] failed_save file={resolved_filename} error={exc}"
        )
    _pipeline_update_stage_sync(
        case_id=case_paths.case_id,
        filename=resolved_filename,
        stage="triage",
        status="completed",
        event="triage_completed",
        details={
            "bucket_seconds": safe_bucket_seconds,
            "cache_status": "miss",
            "force": force,
        },
    )
    payload["case_id"] = case_paths.case_id
    payload["video_url"] = _media_url_for_case_path(case_paths.videos_dir / resolved_filename)
    payload["cache_status"] = "miss"
    return payload


def _load_cached_video_triage_sync(
    *,
    case_id: str,
    filename: str,
    bucket_seconds: float,
) -> dict:
    case_paths, vector_store = _get_vector_store_for_case(case_id)
    resolved_filename, video_path = _resolve_video_path_for_processing(
        case_paths,
        filename,
    )
    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(resolved_filename)
    if not _is_supported_video(video_path.name):
        raise ValueError(
            "Unsupported video format. Allowed extensions: "
            + ", ".join(sorted(VIDEO_EXTENSIONS))
        )

    analysis_summary = vector_store.analysis_summary_by_filename().get(
        resolved_filename,
        {
            "face_people": {"processed": False},
            "vehicles": {"processed": False},
        },
    )
    face_people = (
        analysis_summary.get("face_people")
        if isinstance(analysis_summary.get("face_people"), dict)
        else {}
    )
    vehicles = (
        analysis_summary.get("vehicles")
        if isinstance(analysis_summary.get("vehicles"), dict)
        else {}
    )

    safe_bucket_seconds = max(0.5, float(bucket_seconds))
    video_signature = compute_video_signature(video_path)
    face_people_mtime_ns = _metadata_mtime_ns(case_paths.face_people_metadata_path)
    vehicles_mtime_ns = _metadata_mtime_ns(case_paths.vehicles_metadata_path)
    analysis_signature = _triage_analysis_signature(face_people, vehicles)
    cache_path = _triage_cache_path(
        case_paths,
        resolved_filename,
        safe_bucket_seconds,
    )
    cached_payload = _load_triage_cache_sync(
        cache_path=cache_path,
        bucket_seconds=safe_bucket_seconds,
        video_signature=video_signature,
        analysis_signature=analysis_signature,
        face_people_metadata_mtime_ns=face_people_mtime_ns,
        vehicles_metadata_mtime_ns=vehicles_mtime_ns,
    )
    if not isinstance(cached_payload, dict):
        return {
            "case_id": case_paths.case_id,
            "filename": resolved_filename,
            "bucket_seconds": safe_bucket_seconds,
            "video_url": _media_url_for_case_path(case_paths.videos_dir / resolved_filename),
            "cache_status": "miss",
            "cached": False,
        }

    cached_payload["case_id"] = case_paths.case_id
    cached_payload["filename"] = resolved_filename
    cached_payload["video_url"] = _media_url_for_case_path(
        case_paths.videos_dir / resolved_filename
    )
    cached_payload["cache_status"] = "hit"
    cached_payload["cached"] = True
    return cached_payload


_insights_service = InsightsService(
    app=app,
    resolve_case_id_or_default=_resolve_case_id_or_default,
    get_analysis_store_for_case=_get_analysis_store_for_case,
    hydrate_crop_item=_hydrate_crop_item,
    load_cached_video_triage_sync=_load_cached_video_triage_sync,
    build_video_triage_sync=_build_video_triage_sync,
    get_vector_store_for_case=_get_vector_store_for_case,
    get_temporal_store_for_case=_get_temporal_store_for_case,
    detect_semantic_intent=_detect_semantic_intent,
    apply_semantic_post_filters=_apply_semantic_post_filters,
    media_url_for_case_path=_media_url_for_case_path,
    embedding_engine_info=_embedding_engine_info,
    float_from_env=_float_from_env,
    int_from_env=_int_from_env,
    semantic_object=SEMANTIC_OBJECT,
    semantic_action=SEMANTIC_ACTION,
    semantic_scene=SEMANTIC_SCENE,
)
app.include_router(build_insights_router(insights_service=_insights_service))


def _open_browser() -> None:
    webbrowser.open_new_tab("http://127.0.0.1:8000")


if __name__ == "__main__":
    import uvicorn

    threading.Timer(1.0, _open_browser).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
