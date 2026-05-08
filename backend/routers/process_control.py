from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.process_control import (
    CancelIndexRequest,
    DeleteQueueJobsRequest,
    ShutdownRequest,
)
from backend.services.process_control_service import ProcessControlService


def build_process_control_router(
    *,
    process_control_service: ProcessControlService,
) -> APIRouter:
    router = APIRouter(tags=["process-control"])

    @router.get("/processes")
    async def list_processes() -> dict:
        try:
            return await process_control_service.list_processes()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/shutdown")
    async def graceful_shutdown(request: ShutdownRequest) -> dict:
        try:
            return await process_control_service.graceful_shutdown(confirm=request.confirm)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/processes/index/cancel")
    async def cancel_case_index(request: CancelIndexRequest) -> dict:
        try:
            return await process_control_service.cancel_case_index_jobs(
                case_id=request.case_id,
                force=request.force,
                reason="Cancelled from process control API.",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/processes/queue/delete")
    async def delete_queue_jobs(request: DeleteQueueJobsRequest) -> dict:
        try:
            return await process_control_service.delete_queue_jobs(
                job_ids=request.job_ids,
                cancel_running=request.cancel_running,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return router
