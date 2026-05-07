from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.insights import CropGalleryRequest, SearchRequest, TriageTimelineRequest
from backend.services.insights_service import InsightsService


def build_insights_router(*, insights_service: InsightsService) -> APIRouter:
    router = APIRouter(tags=["insights"])

    @router.post("/analysis_gallery")
    async def analysis_gallery(request: CropGalleryRequest) -> dict:
        return await insights_service.analysis_gallery(
            case_id=request.case_id,
            category=request.category,
            query=request.query,
            top_k=request.top_k,
            limit=request.limit,
        )

    @router.post("/triage_timeline")
    async def triage_timeline(request: TriageTimelineRequest) -> dict:
        return await insights_service.triage_timeline(
            case_id=request.case_id,
            filename=request.filename,
            bucket_seconds=request.bucket_seconds,
            force=request.force,
        )

    @router.post("/search")
    async def search(request: SearchRequest) -> dict:
        return await insights_service.search(
            case_id=request.case_id,
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
            diversity_seconds=request.diversity_seconds,
            oversample_factor=request.oversample_factor,
        )

    return router
