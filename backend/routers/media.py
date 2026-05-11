from __future__ import annotations

from fastapi import APIRouter, File, Query, Request, UploadFile

from backend.schemas.media import (
    AnalysisInterruptedCancelRequest,
    AnalysisStartRequest,
    IndexStartRequest,
    ProcessVideoRequest,
    UploadSessionCompleteRequest,
    UploadSessionStartRequest,
)
from backend.services.media_service import MediaService


def build_media_router(*, media_service: MediaService) -> APIRouter:
    router = APIRouter(tags=["media"])

    @router.post("/upload")
    async def upload(case_id: str | None = None, files: list[UploadFile] = File(...)) -> dict:
        return await media_service.upload(case_id, files)

    @router.post("/upload_session/start")
    async def start_upload_session(request: UploadSessionStartRequest) -> dict:
        return await media_service.start_upload_session(
            case_id=request.case_id,
            files=request.files,
            chunk_size_bytes=request.chunk_size_bytes,
        )

    @router.get("/upload_session/status")
    async def upload_session_status(session_id: str = Query(..., min_length=1)) -> dict:
        return await media_service.get_upload_session_status(session_id=session_id)

    @router.post("/upload_session/chunk")
    async def upload_session_chunk(
        request: Request,
        session_id: str = Query(..., min_length=1),
        file_id: str = Query(..., min_length=1),
        chunk_index: int = Query(..., ge=0),
        total_chunks: int = Query(..., ge=1),
    ) -> dict:
        body = await request.body()
        return await media_service.upload_session_chunk(
            session_id=session_id,
            file_id=file_id,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            chunk_bytes=body,
        )

    @router.post("/upload_session/complete")
    async def complete_upload_session(request: UploadSessionCompleteRequest) -> dict:
        return await media_service.complete_upload_session(session_id=request.session_id)

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
            analysis_face_identity=request.analysis_face_identity,
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

    @router.post("/analysis/start")
    async def start_background_analysis(request: AnalysisStartRequest) -> dict:
        return await media_service.start_background_analysis(
            case_id=request.case_id,
            filenames=request.filenames,
            frame_interval_seconds=request.frame_interval_seconds,
            batch_size=request.batch_size,
            force=request.force,
            analysis_face_people=request.analysis_face_people,
            analysis_vehicles=request.analysis_vehicles,
            analysis_face_identity=request.analysis_face_identity,
        )

    @router.get("/index/status")
    async def get_background_index_status(case_id: str | None = None) -> dict:
        return await media_service.get_background_index_status(case_id)

    @router.get("/analysis/status")
    async def get_background_analysis_status(
        case_id: str | None = None,
        category: str | None = Query(default=None),
        job_id: int | None = Query(default=None, ge=1),
    ) -> dict:
        return await media_service.get_background_analysis_status(case_id, category, job_id)

    # Compatibility alias for older frontend builds.
    @router.post("/analysis/interrupted/cancel_selected")
    @router.post("/analysis/interrupted/cancel")
    async def cancel_interrupted_analysis(request: AnalysisInterruptedCancelRequest) -> dict:
        return await media_service.cancel_interrupted_analysis(
            case_id=request.case_id,
            category=request.category,
            filenames=request.filenames,
        )

    @router.get("/pipeline/status")
    async def get_pipeline_status(
        case_id: str | None = None,
        filename: str | None = None,
    ) -> dict:
        return await media_service.get_pipeline_status(case_id, filename)

    return router
