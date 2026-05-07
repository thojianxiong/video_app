from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.process_control_service import ProcessControlService


class ShutdownRequest(BaseModel):
    confirm: bool = False


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

    return router

