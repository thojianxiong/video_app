from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services.insights_service import InsightsService


class SearchRequest(BaseModel):
    case_id: str | None = None
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    diversity_seconds: float | None = Field(default=None, ge=0.0, le=120.0)
    oversample_factor: int | None = Field(default=None, ge=1, le=50)


class CropGalleryRequest(BaseModel):
    case_id: str | None = None
    category: str = Field(..., pattern="^(face_people|vehicles)$")
    query: str = ""
    top_k: int = Field(default=120, ge=1, le=500)
    limit: int = Field(default=300, ge=1, le=2000)


class TriageTimelineRequest(BaseModel):
    case_id: str | None = None
    filename: str
    bucket_seconds: float = Field(default=1.0, ge=0.5, le=5.0)
    force: bool = False


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

