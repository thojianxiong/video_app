from __future__ import annotations

import asyncio
import os
import shutil
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote

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
    iter_video_frames,
    save_thumbnail,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
VIDEOS_DIR = BASE_DIR / "videos"
THUMBNAILS_DIR = BASE_DIR / "thumbnails"
DATA_DIR = BASE_DIR / "data"
INDEX_PATH = DATA_DIR / "faiss.index"
METADATA_PATH = DATA_DIR / "metadata.json"

for path in (FRONTEND_DIR, VIDEOS_DIR, THUMBNAILS_DIR, DATA_DIR):
    path.mkdir(parents=True, exist_ok=True)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

app = FastAPI(title="Local Video Semantic Search", version="1.0.0")

app.mount("/media/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="media-videos")
app.mount(
    "/media/thumbnails",
    StaticFiles(directory=str(THUMBNAILS_DIR)),
    name="media-thumbnails",
)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class ProcessVideoRequest(BaseModel):
    filename: str
    frame_interval_seconds: float = Field(default=2.0, gt=0)
    batch_size: int = Field(default=32, ge=1, le=256)
    force: bool = False


class SearchRequest(BaseModel):
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
    vector_store = VectorStore(
        index_path=INDEX_PATH,
        metadata_path=METADATA_PATH,
        expected_dimension=embedder.embedding_dim,
    )
    app.state.embedder = embedder
    app.state.vector_store = vector_store


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


def _unique_video_path(filename: str) -> tuple[str, Path]:
    safe_name = _safe_upload_filename(filename)
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix or ".mp4"
    candidate_name = f"{stem}{suffix}"
    candidate_path = VIDEOS_DIR / candidate_name
    counter = 1

    while candidate_path.exists():
        candidate_name = f"{stem}_{counter}{suffix}"
        candidate_path = VIDEOS_DIR / candidate_name
        counter += 1

    return candidate_name, candidate_path


def _write_upload_file(upload: UploadFile, destination: Path) -> None:
    with destination.open("wb") as stream:
        shutil.copyfileobj(upload.file, stream)


def _process_video_sync(
    *,
    filename: str,
    frame_interval_seconds: float,
    batch_size: int,
    force: bool,
) -> dict:
    video_path = VIDEOS_DIR / filename
    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(filename)
    if not _is_supported_video(video_path.name):
        raise ValueError(
            "Unsupported video format. Allowed extensions: "
            + ", ".join(sorted(VIDEO_EXTENSIONS))
        )

    embedder: OpenCLIPEmbedder = app.state.embedder
    vector_store: VectorStore = app.state.vector_store

    signature = compute_video_signature(video_path)
    if vector_store.is_video_indexed(signature, frame_interval_seconds) and not force:
        indexed_frames = vector_store.get_indexed_frame_count(
            signature,
            frame_interval_seconds,
        )
        return {
            "status": "skipped",
            "reason": "video already indexed for this interval",
            "video_filename": filename,
            "indexed_frames": indexed_frames,
        }

    thumbnail_dir = THUMBNAILS_DIR / Path(filename).stem
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
            video_stem=Path(filename).stem,
            timestamp_seconds=frame.timestamp_seconds,
        )
        thumb_rel = thumb_path.relative_to(THUMBNAILS_DIR).as_posix()
        thumb_url = f"/media/thumbnails/{quote(thumb_rel, safe='/')}"
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
                embedder.encode_images(pending_images, batch_size=batch_size)
            )
            pending_images.clear()

    if pending_images:
        embeddings_batches.append(
            embedder.encode_images(pending_images, batch_size=batch_size)
        )

    if embeddings_batches:
        video_embeddings = np.vstack(embeddings_batches).astype(np.float32)
    else:
        video_embeddings = np.empty((0, embedder.embedding_dim), dtype=np.float32)

    upsert_result = vector_store.upsert_video_embeddings(
        signature=signature,
        frame_interval_seconds=frame_interval_seconds,
        video_filename=filename,
        records=records,
        embeddings=video_embeddings,
        force=force,
    )

    upsert_result.update(
        {
            "video_filename": filename,
            "processed_frames": total_frames,
            "frame_interval_seconds": frame_interval_seconds,
        }
    )
    return upsert_result


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded: list[str] = []
    errors: list[str] = []

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

        target_name, target_path = _unique_video_path(upload_file.filename)
        try:
            await asyncio.to_thread(_write_upload_file, upload_file, target_path)
            uploaded.append(target_name)
        except Exception as exc:
            errors.append(f"{upload_file.filename}: {exc}")
        finally:
            await upload_file.close()

    return {"uploaded": uploaded, "errors": errors}


@app.get("/videos")
async def list_videos() -> dict:
    vector_store: VectorStore = app.state.vector_store
    indexed_counts = vector_store.indexed_counts_by_filename()

    videos = []
    for file_path in sorted(VIDEOS_DIR.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        file_stat = file_path.stat()
        videos.append(
            {
                "filename": file_path.name,
                "size_bytes": file_stat.st_size,
                "video_url": f"/media/videos/{quote(file_path.name)}",
                "indexed_frames": indexed_counts.get(file_path.name, 0),
            }
        )

    return {"videos": videos}


@app.post("/process_video")
async def process_video(request: ProcessVideoRequest) -> dict:
    try:
        return await asyncio.to_thread(
            _process_video_sync,
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/search")
async def search(request: SearchRequest) -> dict:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    def _run_search() -> list[dict]:
        embedder: OpenCLIPEmbedder = app.state.embedder
        vector_store: VectorStore = app.state.vector_store
        query_embedding = embedder.encode_text(query)
        raw_results = vector_store.search(query_embedding, top_k=request.top_k)

        hydrated = []
        for item in raw_results:
            hydrated.append(
                {
                    "video_filename": item["video_filename"],
                    "timestamp_seconds": item["timestamp_seconds"],
                    "similarity_score": item["similarity_score"],
                    "thumbnail_url": item["thumbnail_path"],
                    "video_url": f"/media/videos/{quote(item['video_filename'])}",
                }
            )
        return hydrated

    results = await asyncio.to_thread(_run_search)
    return {"query": query, "results": results, "count": len(results)}


def _open_browser() -> None:
    webbrowser.open_new_tab("http://127.0.0.1:8000")


if __name__ == "__main__":
    import uvicorn

    threading.Timer(1.0, _open_browser).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
