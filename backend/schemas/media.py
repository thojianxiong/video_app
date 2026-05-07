from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessVideoRequest(BaseModel):
    case_id: str | None = None
    filename: str
    frame_interval_seconds: float = Field(default=1.0, gt=0)
    batch_size: int = Field(default=32, ge=1, le=256)
    force: bool = False
    analysis_face_people: bool = False
    analysis_vehicles: bool = False
    analysis_only: bool = False


class IndexStartRequest(BaseModel):
    case_id: str | None = None
    filenames: list[str] | None = None
    frame_interval_seconds: float = Field(default=1.0, gt=0)
    batch_size: int = Field(default=32, ge=1, le=256)
    force: bool = False

