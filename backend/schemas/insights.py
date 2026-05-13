from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    case_id: str | None = None
    query: str
    top_k: int = Field(default=120, ge=1, le=500)
    min_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    diversity_seconds: float | None = Field(default=None, ge=0.0, le=120.0)
    oversample_factor: int | None = Field(default=None, ge=1, le=50)
    filenames: list[str] | None = None


class CropGalleryRequest(BaseModel):
    case_id: str | None = None
    category: str = Field(..., pattern="^(face_people|vehicles)$")
    query: str = ""
    top_k: int = Field(default=120, ge=1, le=500)
    limit: int = Field(default=300, ge=1, le=2000)
    filenames: list[str] | None = None


class TriageTimelineRequest(BaseModel):
    case_id: str | None = None
    filename: str
    bucket_seconds: float = Field(default=1.0, ge=0.5, le=5.0)
    force: bool = False
