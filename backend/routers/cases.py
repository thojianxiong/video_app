from __future__ import annotations

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from backend.schemas.cases import CaseCreateRequest, CaseRenameRequest


def build_cases_router(
    *,
    create_case_sync: Callable[[str], dict[str, str]],
    list_cases_sync: Callable[[], list[dict[str, str]]],
    rename_case_sync: Callable[[str, str], dict[str, str]],
    delete_case_sync: Callable[[str], dict[str, str]],
    normalize_case_id: Callable[[str], str],
) -> APIRouter:
    router = APIRouter(tags=["cases"])

    @router.post("/cases")
    async def create_case(request: CaseCreateRequest) -> dict:
        try:
            created = await asyncio.to_thread(create_case_sync, request.name)
            try:
                cases = await asyncio.to_thread(list_cases_sync)
            except Exception:
                cases = []

            if cases is None:
                cases = []
            if not isinstance(cases, list):
                cases = []

            return {
                "case_id": created.get("case_id"),
                "name": created.get("name"),
                "created_at": created.get("created_at"),
                "cases": cases,
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.get("/cases")
    async def list_cases() -> dict:
        try:
            cases = await asyncio.to_thread(list_cases_sync)
        except Exception:
            cases = []

        if cases is None:
            cases = []
        if not isinstance(cases, list):
            cases = []

        return {"cases": cases}

    @router.patch("/cases/{case_id}")
    async def rename_case(case_id: str, request: CaseRenameRequest) -> dict:
        try:
            renamed = await asyncio.to_thread(rename_case_sync, case_id, request.name)
            try:
                cases = await asyncio.to_thread(list_cases_sync)
            except Exception:
                cases = []

            if cases is None:
                cases = []
            if not isinstance(cases, list):
                cases = []

            return {
                "case_id": renamed["case_id"],
                "name": renamed["name"],
                "created_at": renamed.get("created_at"),
                "cases": cases,
            }
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.delete("/cases/{case_id}")
    async def delete_case(case_id: str, request: Request) -> dict:
        try:
            normalized_case_id = normalize_case_id(case_id)
            index_jobs: dict[str, dict] = request.app.state.index_jobs
            index_tasks: dict[str, asyncio.Task] = request.app.state.index_tasks
            index_lock = request.app.state.index_jobs_lock
            with index_lock:
                existing_job = index_jobs.get(normalized_case_id)
                if isinstance(existing_job, dict):
                    existing_status = str(existing_job.get("status") or "")
                    if bool(existing_job.get("running")) or existing_status in {"queued", "running"}:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                f"Background indexing is still running for case {normalized_case_id}. "
                                "Wait for completion before deleting the case."
                            ),
                        )

            deleted = await asyncio.to_thread(delete_case_sync, case_id)
            cache = request.app.state.vector_stores
            cache_lock = request.app.state.vector_stores_lock
            with cache_lock:
                cache.pop(deleted["case_id"], None)

            temporal_cache = request.app.state.temporal_stores
            temporal_cache_lock = request.app.state.temporal_stores_lock
            with temporal_cache_lock:
                temporal_cache.pop(deleted["case_id"], None)

            analysis_cache = request.app.state.analysis_stores
            analysis_cache_lock = request.app.state.analysis_stores_lock
            with analysis_cache_lock:
                analysis_cache.pop(deleted["case_id"], None)

            with index_lock:
                index_jobs.pop(deleted["case_id"], None)
                dangling_task = index_tasks.pop(deleted["case_id"], None)
                if dangling_task and not dangling_task.done():
                    dangling_task.cancel()

            index_job_store = getattr(request.app.state, "index_job_store", None)
            if index_job_store is not None:
                try:
                    await asyncio.to_thread(index_job_store.delete_case, deleted["case_id"])
                except Exception as exc:
                    print(
                        f"[index-persist][{deleted['case_id']}] delete_failed error={exc}"
                    )

            try:
                cases = await asyncio.to_thread(list_cases_sync)
            except Exception:
                cases = []

            if cases is None:
                cases = []
            if not isinstance(cases, list):
                cases = []

            return {
                "deleted_case_id": deleted["case_id"],
                "deleted_name": deleted.get("name"),
                "deleted_created_at": deleted.get("created_at"),
                "cases": cases,
            }
        except HTTPException:
            raise
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return router
