from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.process_control import (
    CancelIndexRequest,
    DeleteQueueJobsRequest,
    RemoveQueueJobFilesRequest,
    RunQueueJobRequest,
    ShutdownRequest,
    StopQueueJobsRequest,
)
from backend.services.process_control_service import ProcessControlService


def build_process_control_router(
    *,
    process_control_service: ProcessControlService,
) -> APIRouter:
    router = APIRouter(tags=["process-control"])

    @router.get("/processes")
    async def list_processes(case_id: str | None = None) -> dict:
        try:
            return await process_control_service.list_processes(case_id=case_id)
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
                case_id=request.case_id,
                job_ids=request.job_ids,
                cancel_running=request.cancel_running,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/processes/queue/stop")
    async def stop_queue_jobs(request: StopQueueJobsRequest) -> dict:
        try:
            return await process_control_service.stop_queue_jobs(
                case_id=request.case_id,
                job_ids=request.job_ids,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/processes/queue/run")
    async def run_queue_job(request: RunQueueJobRequest) -> dict:
        try:
            return await process_control_service.run_queue_job(
                case_id=request.case_id,
                job_id=request.job_id,
                filenames=request.filenames,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/processes/queue/remove_files")
    async def remove_queue_job_files(request: RemoveQueueJobFilesRequest) -> dict:
        try:
            return await process_control_service.remove_queue_job_files(
                case_id=request.case_id,
                job_id=request.job_id,
                filenames=request.filenames,
                allow_running=request.allow_running,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return router
