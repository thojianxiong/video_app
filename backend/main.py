from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import threading
import webbrowser
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from urllib.parse import quote
from uuid import uuid4

import numpy as np
import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from backend.analysis import AnalysisSelection, VideoAnalyzer
from backend.analysis_store import AnalysisCropStore
from backend.embeddings import OpenCLIPEmbedder
from backend.temporal_store import TemporalWindowStore
from backend.vector_store import VectorStore
from backend.video_processing import (
    compute_video_signature,
    convert_to_mp4,
    iter_video_frames,
    save_thumbnail,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
CASES_DIR = BASE_DIR / "cases"
CASES_REGISTRY_PATH = CASES_DIR / "cases.json"
APP_SETTINGS_PATH = CASES_DIR / "app_settings.json"

DEFAULT_OPENCLIP_MODEL = "ViT-L-14"
DEFAULT_OPENCLIP_PRETRAINED = "openai"
DEFAULT_OPENCLIP_DEVICE = "auto"

EMBEDDING_MODEL_PROFILES = [
    {
        "id": "balanced_vit_b32_laion2b",
        "label": "Balanced (ViT-B-32 / LAION2B)",
        "model_name": "ViT-B-32",
        "pretrained": "laion2b_s34b_b79k",
    },
    {
        "id": "high_vit_l14_openai",
        "label": "High Accuracy (ViT-L-14 / OpenAI)",
        "model_name": "ViT-L-14",
        "pretrained": "openai",
    },
]
EMBEDDING_DEVICE_OPTIONS = ["auto", "cuda", "cpu"]

SEMANTIC_OBJECT = "object"
SEMANTIC_ACTION = "action"
SEMANTIC_SCENE = "scene"
SEMANTIC_INTENT_OPTIONS = [SEMANTIC_OBJECT, SEMANTIC_ACTION, SEMANTIC_SCENE]

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

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
CASE_REGISTRY_LOCK = Lock()
APP_SETTINGS_LOCK = Lock()

for path in (FRONTEND_DIR, CASES_DIR):
    path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class CasePaths:
    case_id: str
    case_dir: Path
    videos_dir: Path
    thumbnails_dir: Path
    data_dir: Path
    index_path: Path
    metadata_path: Path
    temporal_index_path: Path
    temporal_metadata_path: Path
    face_people_index_path: Path
    face_people_metadata_path: Path
    vehicles_index_path: Path
    vehicles_metadata_path: Path


app = FastAPI(title="Local Video Semantic Search", version="1.0.0")

app.mount("/media/cases", StaticFiles(directory=str(CASES_DIR)), name="media-cases")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class CaseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class CaseRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ProcessVideoRequest(BaseModel):
    case_id: str | None = None
    filename: str
    frame_interval_seconds: float = Field(default=2.0, gt=0)
    batch_size: int = Field(default=32, ge=1, le=256)
    force: bool = False
    analysis_face_people: bool = False
    analysis_vehicles: bool = False
    analysis_only: bool = False


class SearchRequest(BaseModel):
    case_id: str | None = None
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    diversity_seconds: float | None = Field(default=None, ge=0.0, le=120.0)
    oversample_factor: int | None = Field(default=None, ge=1, le=50)


class EmbeddingSettingsUpdateRequest(BaseModel):
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    pretrained: str | None = Field(default=None, min_length=1, max_length=160)
    device_preference: str | None = Field(default=None, min_length=1, max_length=16)


class CropGalleryRequest(BaseModel):
    case_id: str | None = None
    category: str = Field(..., pattern="^(face_people|vehicles)$")
    query: str = ""
    top_k: int = Field(default=120, ge=1, le=500)
    limit: int = Field(default=300, ge=1, le=2000)


def _non_empty_env(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    cleaned = str(raw).strip()
    return cleaned or None


def _normalize_device_preference(value: str | None) -> str:
    normalized = str(value or DEFAULT_OPENCLIP_DEVICE).strip().lower()
    if normalized not in EMBEDDING_DEVICE_OPTIONS:
        raise ValueError(
            "Invalid device_preference. Allowed values: auto, cuda, cpu."
        )
    return normalized


def _default_embedding_settings() -> dict[str, str]:
    return {
        "model_name": DEFAULT_OPENCLIP_MODEL,
        "pretrained": DEFAULT_OPENCLIP_PRETRAINED,
        "device_preference": DEFAULT_OPENCLIP_DEVICE,
    }


def _load_app_settings_locked() -> dict:
    default_payload = {"embedding": _default_embedding_settings()}
    if not APP_SETTINGS_PATH.exists():
        return default_payload
    try:
        payload = json.loads(APP_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default_payload
    if not isinstance(payload, dict):
        return default_payload
    return payload


def _save_app_settings_locked(payload: dict) -> None:
    APP_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sanitize_embedding_settings(raw_embedding: dict | None) -> dict[str, str]:
    raw = raw_embedding if isinstance(raw_embedding, dict) else {}
    model_name = str(raw.get("model_name") or DEFAULT_OPENCLIP_MODEL).strip()
    pretrained = str(raw.get("pretrained") or DEFAULT_OPENCLIP_PRETRAINED).strip()
    try:
        device_preference = _normalize_device_preference(raw.get("device_preference"))
    except ValueError:
        device_preference = DEFAULT_OPENCLIP_DEVICE
    return {
        "model_name": model_name or DEFAULT_OPENCLIP_MODEL,
        "pretrained": pretrained or DEFAULT_OPENCLIP_PRETRAINED,
        "device_preference": device_preference,
    }


def _read_saved_embedding_settings_sync() -> dict[str, str]:
    with APP_SETTINGS_LOCK:
        payload = _load_app_settings_locked()
        return _sanitize_embedding_settings(payload.get("embedding"))


def _write_saved_embedding_settings_sync(
    *,
    model_name: str,
    pretrained: str,
    device_preference: str,
) -> dict[str, str]:
    clean_model = str(model_name or "").strip()
    clean_pretrained = str(pretrained or "").strip()
    clean_device = _normalize_device_preference(device_preference)
    if not clean_model:
        raise ValueError("model_name cannot be empty")
    if not clean_pretrained:
        raise ValueError("pretrained cannot be empty")

    with APP_SETTINGS_LOCK:
        payload = _load_app_settings_locked()
        payload["embedding"] = {
            "model_name": clean_model,
            "pretrained": clean_pretrained,
            "device_preference": clean_device,
        }
        _save_app_settings_locked(payload)
    return dict(payload["embedding"])


def _embedding_env_overrides() -> dict[str, bool]:
    return {
        "OPENCLIP_MODEL": _non_empty_env("OPENCLIP_MODEL") is not None,
        "OPENCLIP_PRETRAINED": _non_empty_env("OPENCLIP_PRETRAINED") is not None,
        "OPENCLIP_DEVICE": _non_empty_env("OPENCLIP_DEVICE") is not None,
    }


def _resolve_effective_embedding_settings_sync(
    saved_settings: dict[str, str] | None = None,
) -> dict[str, str]:
    saved = saved_settings or _read_saved_embedding_settings_sync()
    model_name = _non_empty_env("OPENCLIP_MODEL") or saved["model_name"]
    pretrained = _non_empty_env("OPENCLIP_PRETRAINED") or saved["pretrained"]
    env_device = _non_empty_env("OPENCLIP_DEVICE")
    if env_device is None:
        device_preference = saved["device_preference"]
    else:
        device_preference = _normalize_device_preference(env_device)

    return {
        "model_name": str(model_name).strip() or DEFAULT_OPENCLIP_MODEL,
        "pretrained": str(pretrained).strip() or DEFAULT_OPENCLIP_PRETRAINED,
        "device_preference": device_preference,
    }


def _find_embedding_profile_id(model_name: str, pretrained: str) -> str | None:
    for profile in EMBEDDING_MODEL_PROFILES:
        if (
            str(profile.get("model_name")) == str(model_name)
            and str(profile.get("pretrained")) == str(pretrained)
        ):
            return str(profile.get("id"))
    return None


def _build_embedding_settings_response_sync() -> dict:
    saved = _read_saved_embedding_settings_sync()
    effective = _resolve_effective_embedding_settings_sync(saved)
    env_overrides = _embedding_env_overrides()

    embedder = getattr(app.state, "embedder", None)
    loaded = {
        "model_name": str(getattr(embedder, "model_name", effective["model_name"])),
        "pretrained": str(getattr(embedder, "pretrained", effective["pretrained"])),
        "device_preference": str(
            getattr(embedder, "device_preference", effective["device_preference"])
        ),
        "device": str(getattr(embedder, "device", "")),
    }
    restart_required = (
        loaded["model_name"] != effective["model_name"]
        or loaded["pretrained"] != effective["pretrained"]
        or loaded["device_preference"] != effective["device_preference"]
    )

    profiles = [dict(profile) for profile in EMBEDDING_MODEL_PROFILES]
    return {
        "loaded": loaded,
        "saved": saved,
        "effective_next_startup": effective,
        "profiles": profiles,
        "device_options": list(EMBEDDING_DEVICE_OPTIONS),
        "loaded_profile_id": _find_embedding_profile_id(
            loaded["model_name"],
            loaded["pretrained"],
        ),
        "saved_profile_id": _find_embedding_profile_id(
            saved["model_name"],
            saved["pretrained"],
        ),
        "effective_profile_id": _find_embedding_profile_id(
            effective["model_name"],
            effective["pretrained"],
        ),
        "env_overrides": env_overrides,
        "restart_required": restart_required,
        "reindex_required_if_model_changes": True,
    }


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


@app.on_event("startup")
async def on_startup() -> None:
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
    app.state.embedder = embedder
    app.state.analyzer = analyzer
    app.state.vector_stores = {}
    app.state.vector_stores_lock = Lock()
    app.state.temporal_stores = {}
    app.state.temporal_stores_lock = Lock()
    app.state.analysis_stores = {}
    app.state.analysis_stores_lock = Lock()
    app.state.embedding_settings = embedding_settings
    app.state.intent_prompt_embeddings = _build_intent_prompt_embeddings(embedder)
    print(
        f"[startup] OpenCLIP model={embedder.model_name} "
        f"pretrained={embedder.pretrained} "
        f"device={embedder.device} "
        f"device_preference={embedder.device_preference}"
    )
    await asyncio.to_thread(_list_cases_sync)


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    index_html = FRONTEND_DIR / "index.html"
    if not index_html.exists():
        raise HTTPException(status_code=500, detail="frontend/index.html not found")
    return FileResponse(str(index_html))


@app.get("/settings/embedding")
async def get_embedding_settings() -> dict:
    try:
        return await asyncio.to_thread(_build_embedding_settings_response_sync)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/settings/embedding")
async def update_embedding_settings(request: EmbeddingSettingsUpdateRequest) -> dict:
    try:
        saved = await asyncio.to_thread(_read_saved_embedding_settings_sync)
        model_name = (
            request.model_name.strip()
            if isinstance(request.model_name, str)
            else saved["model_name"]
        )
        pretrained = (
            request.pretrained.strip()
            if isinstance(request.pretrained, str)
            else saved["pretrained"]
        )
        device_preference = (
            request.device_preference.strip()
            if isinstance(request.device_preference, str)
            else saved["device_preference"]
        )
        await asyncio.to_thread(
            _write_saved_embedding_settings_sync,
            model_name=model_name,
            pretrained=pretrained,
            device_preference=device_preference,
        )
        return await asyncio.to_thread(_build_embedding_settings_response_sync)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    raw = str(case_id or "").strip()
    if not raw:
        raise ValueError("case_id is required")
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in raw)
    if not safe:
        raise ValueError("Invalid case_id")
    return safe


def _build_case_paths(case_id: str) -> CasePaths:
    normalized = _normalize_case_id(case_id)
    case_dir = CASES_DIR / normalized
    videos_dir = case_dir / "videos"
    thumbnails_dir = case_dir / "thumbnails"
    data_dir = case_dir / "data"
    return CasePaths(
        case_id=normalized,
        case_dir=case_dir,
        videos_dir=videos_dir,
        thumbnails_dir=thumbnails_dir,
        data_dir=data_dir,
        index_path=data_dir / "faiss.index",
        metadata_path=data_dir / "metadata.json",
        temporal_index_path=data_dir / "temporal_faiss.index",
        temporal_metadata_path=data_dir / "temporal_metadata.json",
        face_people_index_path=data_dir / "face_people.index",
        face_people_metadata_path=data_dir / "face_people_metadata.json",
        vehicles_index_path=data_dir / "vehicles.index",
        vehicles_metadata_path=data_dir / "vehicles_metadata.json",
    )


def _ensure_case_directories(case_paths: CasePaths) -> None:
    for path in (
        case_paths.case_dir,
        case_paths.videos_dir,
        case_paths.thumbnails_dir,
        case_paths.data_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def _empty_cases_registry() -> dict:
    return {"next_numeric_id": 1, "cases": []}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infer_case_created_at(case_id: str) -> str:
    case_dir = CASES_DIR / case_id
    if case_dir.exists() and case_dir.is_dir():
        try:
            created_at_ts = case_dir.stat().st_ctime
            return datetime.fromtimestamp(created_at_ts, timezone.utc).isoformat()
        except Exception:
            return _utc_now_iso()
    return _utc_now_iso()


def _load_cases_registry_locked() -> dict:
    if not CASES_REGISTRY_PATH.exists():
        return _empty_cases_registry()

    try:
        payload = json.loads(CASES_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _empty_cases_registry()

    if not isinstance(payload, dict):
        return _empty_cases_registry()

    raw_cases = payload.get("cases", [])
    if not isinstance(raw_cases, list):
        raw_cases = []

    cleaned_cases: list[dict[str, str]] = []
    changed = False
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        case_id_raw = item.get("case_id")
        name_raw = item.get("name")
        if case_id_raw is None or name_raw is None:
            continue
        try:
            cleaned_case_id = _normalize_case_id(str(case_id_raw))
        except ValueError:
            continue
        cleaned_name = str(name_raw).strip() or cleaned_case_id
        created_at_raw = item.get("created_at")
        cleaned_created_at = (
            str(created_at_raw).strip()
            if isinstance(created_at_raw, str) and str(created_at_raw).strip()
            else ""
        )
        if not cleaned_created_at:
            cleaned_created_at = _infer_case_created_at(cleaned_case_id)
            changed = True
        cleaned_cases.append(
            {
                "case_id": cleaned_case_id,
                "name": cleaned_name,
                "created_at": cleaned_created_at,
            }
        )

    next_numeric_id = payload.get("next_numeric_id", 1)
    try:
        next_numeric_id = int(next_numeric_id)
    except Exception:
        next_numeric_id = 1
    next_numeric_id = max(1, next_numeric_id)

    if changed:
        payload["next_numeric_id"] = next_numeric_id
        payload["cases"] = cleaned_cases
        _save_cases_registry_locked(payload)

    return {"next_numeric_id": next_numeric_id, "cases": cleaned_cases}


def _save_cases_registry_locked(payload: dict) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    CASES_REGISTRY_PATH.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _find_case_locked(payload: dict, case_id: str) -> dict | None:
    for item in payload.get("cases", []):
        if item.get("case_id") == case_id:
            return item
    return None


def _list_cases_sync() -> list[dict[str, str]]:
    with CASE_REGISTRY_LOCK:
        payload = _load_cases_registry_locked()
        cases = sorted(
            payload["cases"],
            key=lambda item: (
                str(item.get("created_at", "")),
                str(item.get("case_id", "")),
            ),
        )

    for item in cases:
        _ensure_case_directories(_build_case_paths(item["case_id"]))

    return [
        {
            "case_id": item["case_id"],
            "name": item["name"],
            "created_at": str(item.get("created_at", "")),
        }
        for item in cases
    ]


def _create_case_sync(name: str) -> dict[str, str]:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("Case name cannot be empty")

    with CASE_REGISTRY_LOCK:
        payload = _load_cases_registry_locked()
        existing_ids = {
            str(item.get("case_id"))
            for item in payload.get("cases", [])
            if item.get("case_id")
        }

        case_id = str(uuid4())
        while case_id in existing_ids:
            case_id = str(uuid4())

        created_at = _utc_now_iso()
        payload["cases"].append(
            {
                "case_id": case_id,
                "name": clean_name,
                "created_at": created_at,
            }
        )
        _save_cases_registry_locked(payload)

    _ensure_case_directories(_build_case_paths(case_id))
    return {"case_id": case_id, "name": clean_name, "created_at": created_at}


def _delete_case_sync(case_id: str) -> dict[str, str]:
    normalized = _normalize_case_id(case_id)

    with CASE_REGISTRY_LOCK:
        payload = _load_cases_registry_locked()
        existing_cases = payload.get("cases", [])
        remaining_cases: list[dict[str, str]] = []
        deleted_case: dict | None = None

        for item in existing_cases:
            if item.get("case_id") == normalized and deleted_case is None:
                deleted_case = item
            else:
                remaining_cases.append(item)

        if deleted_case is None:
            raise KeyError(normalized)

        payload["cases"] = remaining_cases
        _save_cases_registry_locked(payload)

    case_paths = _build_case_paths(normalized)
    if case_paths.case_dir.exists():
        shutil.rmtree(case_paths.case_dir)

    deleted_name = str(deleted_case.get("name") or normalized)
    deleted_created_at = str(deleted_case.get("created_at") or "")
    return {
        "case_id": normalized,
        "name": deleted_name,
        "created_at": deleted_created_at,
    }


def _rename_case_sync(case_id: str, name: str) -> dict[str, str]:
    normalized = _normalize_case_id(case_id)
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("Case name cannot be empty")

    with CASE_REGISTRY_LOCK:
        payload = _load_cases_registry_locked()
        case = _find_case_locked(payload, normalized)
        if case is None:
            raise KeyError(normalized)
        case["name"] = clean_name
        _save_cases_registry_locked(payload)

    return {
        "case_id": normalized,
        "name": clean_name,
        "created_at": str(case.get("created_at") or ""),
    }


def _get_case_paths_or_raise(case_id: str) -> CasePaths:
    normalized = _normalize_case_id(case_id)
    with CASE_REGISTRY_LOCK:
        payload = _load_cases_registry_locked()
        case = _find_case_locked(payload, normalized)
    if case is None:
        raise KeyError(normalized)

    case_paths = _build_case_paths(normalized)
    _ensure_case_directories(case_paths)
    return case_paths


def _resolve_case_id_or_default(case_id: str | None) -> str:
    if case_id and str(case_id).strip():
        return _normalize_case_id(case_id)

    cases = _list_cases_sync()
    if cases:
        return _normalize_case_id(cases[0]["case_id"])

    raise ValueError("No cases available. Create a case first.")


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
        else:
            thumbnail_dir = case_paths.thumbnails_dir / Path(resolved_filename).stem
            if force and thumbnail_dir.exists():
                shutil.rmtree(thumbnail_dir)
            thumbnail_dir.mkdir(parents=True, exist_ok=True)

            records: list[dict] = []
            embeddings_batches: list[np.ndarray] = []
            pending_images: list[Image.Image] = []
            total_frames = 0

            for frame in iter_video_frames(video_path, interval_seconds=frame_interval_seconds):
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

                if len(pending_images) >= batch_size:
                    embeddings_batches.append(
                        app.state.embedder.encode_images(pending_images, batch_size=batch_size)
                    )
                    pending_images.clear()

            if pending_images:
                embeddings_batches.append(
                    app.state.embedder.encode_images(pending_images, batch_size=batch_size)
                )

            if embeddings_batches:
                video_embeddings = np.vstack(embeddings_batches).astype(np.float32)
            else:
                video_embeddings = np.empty((0, app.state.embedder.embedding_dim), dtype=np.float32)

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

    vector_result = vector_store.delete_video_embeddings(safe_filename)
    temporal_result = temporal_store.delete_video_windows(safe_filename)
    crop_result = analysis_store.delete_video(safe_filename)
    video_path.unlink(missing_ok=True)

    thumbnail_dir = case_paths.thumbnails_dir / Path(safe_filename).stem
    if thumbnail_dir.exists():
        shutil.rmtree(thumbnail_dir, ignore_errors=True)
    detections_dir = case_paths.thumbnails_dir / "detections" / Path(safe_filename).stem
    if detections_dir.exists():
        shutil.rmtree(detections_dir, ignore_errors=True)

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


@app.post("/cases")
async def create_case(request: CaseCreateRequest) -> dict:
    try:
        created = await asyncio.to_thread(_create_case_sync, request.name)
        try:
            cases = await asyncio.to_thread(_list_cases_sync)
        except Exception:
            cases = []

        if cases is None:
            cases = []
        if not isinstance(cases, list):
            cases = []

        return {
            "case_id": created.get("case_id"),
            "name": created.get("name"),
            "created_at": created.get("created_at"),
            "cases": cases,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/cases")
async def list_cases() -> dict:
    try:
        cases = await asyncio.to_thread(_list_cases_sync)
    except Exception:
        cases = []

    if cases is None:
        cases = []
    if not isinstance(cases, list):
        cases = []

    return {"cases": cases}


@app.patch("/cases/{case_id}")
async def rename_case(case_id: str, request: CaseRenameRequest) -> dict:
    try:
        renamed = await asyncio.to_thread(_rename_case_sync, case_id, request.name)
        try:
            cases = await asyncio.to_thread(_list_cases_sync)
        except Exception:
            cases = []

        if cases is None:
            cases = []
        if not isinstance(cases, list):
            cases = []

        return {
            "case_id": renamed["case_id"],
            "name": renamed["name"],
            "created_at": renamed.get("created_at"),
            "cases": cases,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/cases/{case_id}")
async def delete_case(case_id: str) -> dict:
    try:
        deleted = await asyncio.to_thread(_delete_case_sync, case_id)
        cache: dict[str, VectorStore] = app.state.vector_stores
        cache_lock: Lock = app.state.vector_stores_lock
        with cache_lock:
            cache.pop(deleted["case_id"], None)
        temporal_cache: dict[str, TemporalWindowStore] = app.state.temporal_stores
        temporal_cache_lock: Lock = app.state.temporal_stores_lock
        with temporal_cache_lock:
            temporal_cache.pop(deleted["case_id"], None)
        analysis_cache: dict[str, AnalysisCropStore] = app.state.analysis_stores
        analysis_cache_lock: Lock = app.state.analysis_stores_lock
        with analysis_cache_lock:
            analysis_cache.pop(deleted["case_id"], None)

        try:
            cases = await asyncio.to_thread(_list_cases_sync)
        except Exception:
            cases = []

        if cases is None:
            cases = []
        if not isinstance(cases, list):
            cases = []

        return {
            "deleted_case_id": deleted["case_id"],
            "deleted_name": deleted.get("name"),
            "deleted_created_at": deleted.get("created_at"),
            "cases": cases,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/upload")
async def upload(case_id: str | None = None, files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        resolved_case_id = await asyncio.to_thread(_resolve_case_id_or_default, case_id)
        case_paths = await asyncio.to_thread(_get_case_paths_or_raise, resolved_case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    uploaded: list[str] = []
    errors: list[str] = []
    transcoded: list[dict[str, str]] = []

    for upload_file in files:
        if not upload_file.filename:
            errors.append("Encountered a file without a name")
            continue
        if not _is_supported_video(upload_file.filename):
            errors.append(
                f"{upload_file.filename}: unsupported format (allowed: "
                + ", ".join(sorted(VIDEO_EXTENSIONS))
                + ")"
            )
            await upload_file.close()
            continue

        source_extension = Path(upload_file.filename).suffix.lower() or ".mp4"
        temp_upload_path = case_paths.data_dir / f"upload_{uuid4().hex}{source_extension}"
        converted_name, converted_path = _unique_video_path(
            case_paths.videos_dir,
            upload_file.filename,
            forced_suffix=".mp4",
        )
        try:
            await asyncio.to_thread(_write_upload_file, upload_file, temp_upload_path)

            print(
                f"[upload][{case_paths.case_id}] convert input={upload_file.filename} "
                f"output={converted_name}"
            )
            conversion_ok, conversion_error = await asyncio.to_thread(
                convert_to_mp4,
                temp_upload_path,
                converted_path,
            )

            if conversion_ok:
                temp_upload_path.unlink(missing_ok=True)
                uploaded.append(converted_name)
                transcoded.append(
                    {
                        "source_filename": upload_file.filename,
                        "stored_filename": converted_name,
                    }
                )
                print(
                    f"[upload][{case_paths.case_id}] convert success input={upload_file.filename} "
                    f"output={converted_name}"
                )
            else:
                fallback_name, fallback_path = _unique_video_path(
                    case_paths.videos_dir,
                    upload_file.filename,
                )
                await asyncio.to_thread(shutil.move, str(temp_upload_path), str(fallback_path))
                uploaded.append(fallback_name)
                short_error = _truncate_error(conversion_error)
                errors.append(
                    f"{upload_file.filename}: mp4 conversion failed ({short_error})"
                )
                print(
                    f"[upload][{case_paths.case_id}] convert failure input={upload_file.filename} "
                    f"output={converted_name}"
                )
                if conversion_error:
                    print(f"[upload][{case_paths.case_id}] ffmpeg error: {conversion_error}")
        except Exception as exc:
            converted_path.unlink(missing_ok=True)
            temp_upload_path.unlink(missing_ok=True)
            errors.append(f"{upload_file.filename}: {exc}")
        finally:
            await upload_file.close()

    return {
        "case_id": case_paths.case_id,
        "uploaded": uploaded,
        "errors": errors,
        "transcoded": transcoded,
    }


@app.get("/videos")
async def list_videos(case_id: str | None = None) -> dict:
    try:
        resolved_case_id = await asyncio.to_thread(_resolve_case_id_or_default, case_id)
        case_paths, vector_store = await asyncio.to_thread(
            _get_vector_store_for_case,
            resolved_case_id,
        )
        _, temporal_store = await asyncio.to_thread(
            _get_temporal_store_for_case,
            resolved_case_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    indexed_counts = vector_store.indexed_counts_by_filename()
    indexed_window_counts = temporal_store.indexed_counts_by_filename()
    analysis_summary = vector_store.analysis_summary_by_filename()
    videos = []

    for file_path in sorted(case_paths.videos_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        file_stat = file_path.stat()
        videos.append(
            {
                "filename": file_path.name,
                "size_bytes": file_stat.st_size,
                "video_url": _media_url_for_case_path(file_path),
                "indexed_frames": indexed_counts.get(file_path.name, 0),
                "indexed_windows": indexed_window_counts.get(file_path.name, 0),
                "analysis": analysis_summary.get(
                    file_path.name,
                    {
                        "processed_frames": 0,
                        "face_people": {
                            "processed": False,
                            "face_count": 0,
                            "people_count": 0,
                            "hit_frames": 0,
                            "first_hit_seconds": None,
                        },
                        "vehicles": {
                            "processed": False,
                            "vehicle_count": 0,
                            "hit_frames": 0,
                            "first_hit_seconds": None,
                        },
                    },
                ),
            }
        )

    return {"case_id": case_paths.case_id, "videos": videos}


@app.delete("/videos")
async def delete_video(case_id: str | None = None, filename: str | None = None) -> dict:
    if not filename or not str(filename).strip():
        raise HTTPException(status_code=400, detail="filename is required")

    try:
        resolved_case_id = await asyncio.to_thread(_resolve_case_id_or_default, case_id)
        return await asyncio.to_thread(_delete_video_sync, resolved_case_id, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Video not found: {filename}")
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/process_video")
async def process_video(request: ProcessVideoRequest) -> dict:
    try:
        resolved_case_id = await asyncio.to_thread(
            _resolve_case_id_or_default,
            request.case_id,
        )
        return await asyncio.to_thread(
            _process_video_sync,
            case_id=resolved_case_id,
            filename=request.filename,
            frame_interval_seconds=request.frame_interval_seconds,
            batch_size=request.batch_size,
            force=request.force,
            analysis_face_people=request.analysis_face_people,
            analysis_vehicles=request.analysis_vehicles,
            analysis_only=request.analysis_only,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video not found: {request.filename}",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {request.case_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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


@app.post("/analysis_gallery")
async def analysis_gallery(request: CropGalleryRequest) -> dict:
    try:
        selected_case_id = await asyncio.to_thread(
            _resolve_case_id_or_default,
            request.case_id,
        )
        case_paths, crop_store = await asyncio.to_thread(
            _get_analysis_store_for_case,
            selected_case_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {request.case_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    query = request.query.strip()
    category = request.category

    try:
        if query:
            query_embedding = await asyncio.to_thread(app.state.embedder.encode_text, query)
            raw_items = await asyncio.to_thread(
                crop_store.search,
                category=category,
                query_embedding=query_embedding,
                top_k=request.top_k,
            )
        else:
            raw_items = await asyncio.to_thread(
                crop_store.list_items,
                category=category,
                limit=request.limit,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    faces: list[dict] = []
    people: list[dict] = []
    vehicles: list[dict] = []
    for item in raw_items:
        hydrated = _hydrate_crop_item(case_paths, item)
        kind = str(hydrated.get("kind") or "").lower()
        if category == AnalysisCropStore.FACE_PEOPLE:
            if kind == "face":
                faces.append(hydrated)
            else:
                people.append(hydrated)
        else:
            vehicles.append(hydrated)

    return {
        "case_id": case_paths.case_id,
        "category": category,
        "query": query,
        "faces": faces,
        "people": people,
        "vehicles": vehicles,
        "count": len(raw_items),
    }


@app.post("/search")
async def search(request: SearchRequest) -> dict:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    min_score = (
        float(request.min_score)
        if request.min_score is not None
        else _float_from_env("SEMANTIC_MIN_SCORE", 0.22)
    )
    diversity_seconds = (
        float(request.diversity_seconds)
        if request.diversity_seconds is not None
        else _float_from_env("SEMANTIC_DIVERSITY_SECONDS", 6.0)
    )
    oversample_factor = (
        int(request.oversample_factor)
        if request.oversample_factor is not None
        else _int_from_env("SEMANTIC_OVERSAMPLE_FACTOR", 10)
    )
    max_candidates = max(1, _int_from_env("SEMANTIC_MAX_CANDIDATES", 2000))
    search_top_k = min(
        max(int(request.top_k), int(request.top_k) * max(1, oversample_factor)),
        max_candidates,
    )

    def _run_search(resolved_case_id: str) -> tuple[str, list[dict], dict[str, Any]]:
        case_paths, vector_store = _get_vector_store_for_case(resolved_case_id)
        _, temporal_store = _get_temporal_store_for_case(resolved_case_id)
        query_embedding = app.state.embedder.encode_text(query)
        intent_payload = _detect_semantic_intent(query, query_embedding)
        intent = str(intent_payload.get("intent") or SEMANTIC_OBJECT)
        mode = "frame"
        fallback_used = False
        active_min_score = float(min_score)
        active_diversity = float(diversity_seconds)

        if intent == SEMANTIC_ACTION:
            mode = "temporal"
            active_diversity = max(active_diversity, 8.0)
            active_min_score = max(-1.0, active_min_score - 0.03)
            raw_results = temporal_store.search(query_embedding, top_k=search_top_k)
            if not raw_results:
                fallback_used = True
                mode = "frame_fallback"
                raw_results = vector_store.search(query_embedding, top_k=search_top_k)
        elif intent == SEMANTIC_SCENE:
            mode = "temporal"
            active_diversity = max(active_diversity, 10.0)
            active_min_score = max(-1.0, active_min_score - 0.02)
            raw_results = temporal_store.search(query_embedding, top_k=search_top_k)
            if not raw_results:
                fallback_used = True
                mode = "frame_fallback"
                raw_results = vector_store.search(query_embedding, top_k=search_top_k)
        else:
            raw_results = vector_store.search(query_embedding, top_k=search_top_k)

        filtered_results = _apply_semantic_post_filters(
            raw_results,
            top_k=request.top_k,
            min_score=active_min_score,
            diversity_seconds=active_diversity,
        )

        if not filtered_results and mode == "temporal":
            fallback_used = True
            mode = "frame_fallback"
            raw_results = vector_store.search(query_embedding, top_k=search_top_k)
            filtered_results = _apply_semantic_post_filters(
                raw_results,
                top_k=request.top_k,
                min_score=min_score,
                diversity_seconds=diversity_seconds,
            )

        print(
            f"[semantic][{case_paths.case_id}] query={query!r} "
            f"intent={intent} mode={mode} fallback={fallback_used} "
            f"top_k={request.top_k} searched={search_top_k} "
            f"raw={len(raw_results)} filtered={len(filtered_results)} "
            f"min_score={active_min_score:.3f} diversity_seconds={active_diversity:.2f}"
        )

        hydrated = []
        for item in filtered_results:
            payload = {
                "video_filename": item["video_filename"],
                "timestamp_seconds": item["timestamp_seconds"],
                "similarity_score": item["similarity_score"],
                "thumbnail_url": item["thumbnail_path"],
                "video_url": _media_url_for_case_path(
                    case_paths.videos_dir / item["video_filename"]
                ),
            }
            if "start_seconds" in item:
                payload["window_start_seconds"] = float(item.get("start_seconds", 0.0))
            if "end_seconds" in item:
                payload["window_end_seconds"] = float(item.get("end_seconds", 0.0))
            hydrated.append(payload)

        return case_paths.case_id, hydrated, {
            "intent": intent,
            "intent_scores": intent_payload.get("scores", {}),
            "intent_margin": float(intent_payload.get("margin", 0.0)),
            "intent_reasons": intent_payload.get("reasons", []),
            "search_mode": mode,
            "fallback_used": fallback_used,
            "effective_min_score": float(active_min_score),
            "effective_diversity_seconds": float(active_diversity),
        }

    try:
        selected_case_id = await asyncio.to_thread(
            _resolve_case_id_or_default,
            request.case_id,
        )
        resolved_case_id, results, search_meta = await asyncio.to_thread(
            _run_search,
            selected_case_id,
        )
        return {
            "case_id": resolved_case_id,
            "query": query,
            "results": results,
            "count": len(results),
            "intent": search_meta.get("intent"),
            "search_mode": search_meta.get("search_mode"),
            "fallback_used": bool(search_meta.get("fallback_used")),
            "intent_scores": search_meta.get("intent_scores", {}),
            "intent_margin": float(search_meta.get("intent_margin", 0.0)),
            "intent_reasons": search_meta.get("intent_reasons", []),
            "embedding_engine": _embedding_engine_info(),
            "search_settings": {
                "top_k": int(request.top_k),
                "min_score": float(search_meta.get("effective_min_score", min_score)),
                "diversity_seconds": float(
                    search_meta.get("effective_diversity_seconds", diversity_seconds)
                ),
                "oversample_factor": int(oversample_factor),
                "candidates_searched": int(search_top_k),
                "intent_auto": True,
            },
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {request.case_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _open_browser() -> None:
    webbrowser.open_new_tab("http://127.0.0.1:8000")


if __name__ == "__main__":
    import uvicorn

    threading.Timer(1.0, _open_browser).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
