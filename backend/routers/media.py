from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from backend.schemas.media import IndexStartRequest, ProcessVideoRequest
from backend.services.media_service import MediaService


def build_media_router(*, media_service: MediaService) -> APIRouter:
    router = APIRouter(tags=["media"])

    @router.post("/upload")
    async def upload(case_id: str | None = None, files: list[UploadFile] = File(...)) -> dict:
        return await media_service.upload(case_id, files)

    @router.get("/videos")
    async def list_videos(case_id: str | None = None) -> dict:
        return await media_service.list_videos(case_id)

    @router.delete("/videos")
    async def delete_video(case_id: str | None = None, filename: str | None = None) -> dict:
        return await media_service.delete_video(case_id, filename)

    @router.post("/process_video")
    async def process_video(request: ProcessVideoRequest) -> dict:
        return await media_service.process_video(
            case_id=request.case_id,
            filename=request.filename,
            frame_interval_seconds=request.frame_interval_seconds,
            batch_size=request.batch_size,
            force=request.force,
            analysis_face_people=request.analysis_face_people,
            analysis_vehicles=request.analysis_vehicles,
            analysis_only=request.analysis_only,
        )

    @router.post("/index/start")
    async def start_background_index(request: IndexStartRequest) -> dict:
        return await media_service.start_background_index(
            case_id=request.case_id,
            filenames=request.filenames,
            frame_interval_seconds=request.frame_interval_seconds,
            batch_size=request.batch_size,
            force=request.force,
        )

    @router.get("/index/status")
    async def get_background_index_status(case_id: str | None = None) -> dict:
        return await media_service.get_background_index_status(case_id)

    return router
