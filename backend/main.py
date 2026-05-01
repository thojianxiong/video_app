from __future__ import annotations

import asyncio
import json
import os
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
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from backend.embeddings import OpenCLIPEmbedder
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

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
CASE_REGISTRY_LOCK = Lock()

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


class SearchRequest(BaseModel):
    case_id: str | None = None
    query: str
    top_k: int = Field(default=10, ge=1, le=100)


@app.on_event("startup")
async def on_startup() -> None:
    embedder = await asyncio.to_thread(
        OpenCLIPEmbedder,
        os.getenv("OPENCLIP_MODEL", "ViT-B-32"),
        os.getenv("OPENCLIP_PRETRAINED", "laion2b_s34b_b79k"),
        os.getenv("OPENCLIP_CACHE_DIR"),
    )
    app.state.embedder = embedder
    app.state.vector_stores = {}
    app.state.vector_stores_lock = Lock()
    await asyncio.to_thread(_list_cases_sync)


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


def _get_vector_store_for_case(case_id: str) -> tuple[CasePaths, VectorStore]:
    case_paths = _get_case_paths_or_raise(case_id)
    embedder: OpenCLIPEmbedder = app.state.embedder
    cache: dict[str, VectorStore] = app.state.vector_stores
    cache_lock: Lock = app.state.vector_stores_lock

    with cache_lock:
        store = cache.get(case_paths.case_id)
        if store is None:
            store = VectorStore(
                index_path=case_paths.index_path,
                metadata_path=case_paths.metadata_path,
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


def _media_url_for_case_path(path: Path) -> str:
    relative = path.relative_to(CASES_DIR).as_posix()
    return f"/media/cases/{quote(relative, safe='/')}"


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


def _process_video_sync(
    *,
    case_id: str,
    filename: str,
    frame_interval_seconds: float,
    batch_size: int,
    force: bool,
) -> dict:
    case_paths, vector_store = _get_vector_store_for_case(case_id)
    resolved_filename, video_path = _resolve_video_path_for_processing(case_paths, filename)

    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(filename)
    if not _is_supported_video(video_path.name):
        raise ValueError(
            "Unsupported video format. Allowed extensions: "
            + ", ".join(sorted(VIDEO_EXTENSIONS))
        )

    signature = compute_video_signature(video_path)
    if vector_store.is_video_indexed(signature, frame_interval_seconds) and not force:
        indexed_frames = vector_store.get_indexed_frame_count(
            signature,
            frame_interval_seconds,
        )
        return {
            "status": "skipped",
            "reason": "video already indexed for this interval",
            "case_id": case_paths.case_id,
            "video_filename": resolved_filename,
            "indexed_frames": indexed_frames,
        }

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

    upsert_result = vector_store.upsert_video_embeddings(
        signature=signature,
        frame_interval_seconds=frame_interval_seconds,
        video_filename=resolved_filename,
        records=records,
        embeddings=video_embeddings,
        force=force,
    )

    upsert_result.update(
        {
            "case_id": case_paths.case_id,
            "video_filename": resolved_filename,
            "processed_frames": total_frames,
            "frame_interval_seconds": frame_interval_seconds,
        }
    )
    return upsert_result


def _delete_video_sync(case_id: str, filename: str) -> dict:
    case_paths, vector_store = _get_vector_store_for_case(case_id)
    safe_filename = Path(str(filename or "")).name.strip()
    if not safe_filename:
        raise ValueError("filename is required")

    video_path = case_paths.videos_dir / safe_filename
    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(safe_filename)

    vector_result = vector_store.delete_video_embeddings(safe_filename)
    video_path.unlink(missing_ok=True)

    thumbnail_dir = case_paths.thumbnails_dir / Path(safe_filename).stem
    if thumbnail_dir.exists():
        shutil.rmtree(thumbnail_dir, ignore_errors=True)

    return {
        "case_id": case_paths.case_id,
        "filename": safe_filename,
        "deleted": True,
        "removed_vectors": int(vector_result.get("removed_vectors", 0)),
        "removed_records": int(vector_result.get("removed_records", 0)),
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    indexed_counts = vector_store.indexed_counts_by_filename()
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


@app.post("/search")
async def search(request: SearchRequest) -> dict:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    def _run_search(resolved_case_id: str) -> tuple[str, list[dict]]:
        case_paths, vector_store = _get_vector_store_for_case(resolved_case_id)
        query_embedding = app.state.embedder.encode_text(query)
        raw_results = vector_store.search(query_embedding, top_k=request.top_k)

        hydrated = []
        for item in raw_results:
            hydrated.append(
                {
                    "video_filename": item["video_filename"],
                    "timestamp_seconds": item["timestamp_seconds"],
                    "similarity_score": item["similarity_score"],
                    "thumbnail_url": item["thumbnail_path"],
                    "video_url": _media_url_for_case_path(
                        case_paths.videos_dir / item["video_filename"]
                    ),
                }
            )
        return case_paths.case_id, hydrated

    try:
        selected_case_id = await asyncio.to_thread(
            _resolve_case_id_or_default,
            request.case_id,
        )
        resolved_case_id, results = await asyncio.to_thread(_run_search, selected_case_id)
        return {
            "case_id": resolved_case_id,
            "query": query,
            "results": results,
            "count": len(results),
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
