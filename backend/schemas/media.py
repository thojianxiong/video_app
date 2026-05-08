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


class AnalysisStartRequest(BaseModel):
    case_id: str | None = None
    filenames: list[str] | None = None
    frame_interval_seconds: float = Field(default=1.0, gt=0)
    batch_size: int = Field(default=32, ge=1, le=256)
    force: bool = False
    analysis_face_people: bool = False
    analysis_vehicles: bool = False


class AnalysisInterruptedCancelRequest(BaseModel):
    case_id: str | None = None
    category: str = Field(min_length=1)
    filenames: list[str] = Field(min_length=1)


class UploadSessionFileDescriptor(BaseModel):
    source_index: int = Field(default=0, ge=0)
    source_filename: str = Field(min_length=1)
    source_size: int = Field(ge=0)
    source_last_modified_ms: int | None = Field(default=None, ge=0)
    source_key: str = Field(min_length=1, max_length=1024)


class UploadSessionStartRequest(BaseModel):
    case_id: str | None = None
    chunk_size_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=64 * 1024 * 1024)
    files: list[UploadSessionFileDescriptor] = Field(min_length=1)


class UploadSessionCompleteRequest(BaseModel):
    session_id: str = Field(min_length=1)
