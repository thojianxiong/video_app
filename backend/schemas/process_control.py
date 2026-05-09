from __future__ import annotations

from pydantic import BaseModel


class ShutdownRequest(BaseModel):
    confirm: bool = False


class CancelIndexRequest(BaseModel):
    case_id: str
    force: bool = False


class DeleteQueueJobsRequest(BaseModel):
    job_ids: list[int]
    cancel_running: bool = True


class RemoveQueueJobFilesRequest(BaseModel):
    job_id: int
    filenames: list[str]
