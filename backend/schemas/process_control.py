from __future__ import annotations

from pydantic import BaseModel, Field


class ShutdownRequest(BaseModel):
    confirm: bool = False


class CancelIndexRequest(BaseModel):
    case_id: str
    force: bool = False


class DeleteQueueJobsRequest(BaseModel):
    case_id: str
    job_ids: list[int]
    cancel_running: bool = False


class StopQueueJobsRequest(BaseModel):
    case_id: str
    job_ids: list[int]


class RunQueueJobRequest(BaseModel):
    case_id: str
    job_id: int
    filenames: list[str] = Field(default_factory=list)


class RemoveQueueJobFilesRequest(BaseModel):
    case_id: str
    job_id: int
    filenames: list[str]
    allow_running: bool = False
