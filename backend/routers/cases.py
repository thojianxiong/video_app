from __future__ import annotations

import asyncio
from collections.abc import Callable
from threading import Lock

from fastapi import APIRouter, HTTPException, Request
from backend.schemas.cases import CaseCreateRequest, CaseRenameRequest


def build_cases_router(
    *,
    create_case_sync: Callable[[str], dict[str, str]],
    list_cases_sync: Callable[[], list[dict[str, str]]],
    rename_case_sync: Callable[[str, str], dict[str, str]],
    delete_case_sync: Callable[[str], dict[str, str]],
    normalize_case_id: Callable[[str], str],
    delete_quiescence_timeout_seconds: float = 15.0,
    delete_poll_interval_seconds: float = 0.25,
    delete_required_quiet_polls: int = 2,
) -> APIRouter:
    router = APIRouter(tags=["cases"])

    def _ensure_case_delete_guard(request: Request) -> tuple[object, set[str]]:
        state = request.app.state
        guard_lock = getattr(state, "deleting_case_ids_lock", None)
        if guard_lock is None or not hasattr(guard_lock, "acquire"):
            guard_lock = Lock()
            setattr(state, "deleting_case_ids_lock", guard_lock)

        deleting_cases = getattr(state, "deleting_case_ids", None)
        if not isinstance(deleting_cases, set):
            deleting_cases = set()
            setattr(state, "deleting_case_ids", deleting_cases)

        # Backward compatibility for older code paths that may still inspect these keys.
        setattr(state, "case_delete_guard_lock", guard_lock)
        setattr(state, "case_delete_in_progress", deleting_cases)

        return guard_lock, deleting_cases

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
        normalized_case_id = ""
        guard_lock: object | None = None
        deleting_cases: set[str] | None = None
        guard_acquired = False
        try:
            normalized_case_id = normalize_case_id(case_id)
            guard_lock, deleting_cases = _ensure_case_delete_guard(request)
            with guard_lock:
                if normalized_case_id in deleting_cases:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Case {normalized_case_id} is already being deleted. "
                            "Please retry shortly."
                        ),
                    )
                deleting_cases.add(normalized_case_id)
                guard_acquired = True

            index_jobs: dict[str, dict] = request.app.state.index_jobs
            index_tasks: dict[str, asyncio.Task] = request.app.state.index_tasks
            index_lock = request.app.state.index_jobs_lock
            index_queue_store = getattr(request.app.state, "index_queue_store", None)
            process_control_service = getattr(request.app.state, "process_control_service", None)
            cancel_requested = False
            queue_cancelled_count = 0
            task_cancelled = False

            async def _case_has_active_index_processes() -> tuple[bool, str]:
                with index_lock:
                    job = index_jobs.get(normalized_case_id)
                    task = index_tasks.get(normalized_case_id)
                    task_active = isinstance(task, asyncio.Task) and not task.done()
                    if isinstance(job, dict):
                        status = str(job.get("status") or "").strip().lower()
                        if (
                            bool(job.get("running"))
                            or task_active
                            or status in {"running", "deleting"}
                        ):
                            current_file = str(job.get("current_filename") or "").strip()
                            if current_file:
                                return True, current_file
                            return True, ""
                    if task_active:
                        return True, ""

                queue_running_cases = getattr(request.app.state, "queue_running_case_ids", None)
                queue_running_cases_lock = getattr(
                    request.app.state,
                    "queue_running_case_ids_lock",
                    None,
                )
                if isinstance(queue_running_cases, set):
                    if queue_running_cases_lock is not None and hasattr(
                        queue_running_cases_lock,
                        "acquire",
                    ):
                        with queue_running_cases_lock:
                            if normalized_case_id in queue_running_cases:
                                return True, ""
                    elif normalized_case_id in queue_running_cases:
                        return True, ""

                if index_queue_store is not None:
                    try:
                        active_queue_job = await asyncio.to_thread(
                            index_queue_store.get_case_active,
                            normalized_case_id,
                        )
                        if isinstance(active_queue_job, dict):
                            payload = active_queue_job.get("payload") or {}
                            filenames = payload.get("filenames") or []
                            if isinstance(filenames, list) and filenames:
                                return True, str(filenames[0] or "").strip()
                            return True, ""
                    except Exception as exc:
                        print(
                            f"[case-delete][{normalized_case_id}] queue_status_check_failed error={exc}"
                        )
                        return True, ""
                return False, ""

            async def _request_case_stop(*, reason: str) -> None:
                nonlocal cancel_requested, queue_cancelled_count, task_cancelled
                if process_control_service is not None:
                    try:
                        cancel_payload = await process_control_service.cancel_case_index_jobs(
                            case_id=normalized_case_id,
                            force=True,
                            reason=reason,
                        )
                        if isinstance(cancel_payload, dict):
                            cancel_requested = (
                                cancel_requested
                                or bool(cancel_payload.get("cancel_requested", False))
                            )
                            task_cancelled = task_cancelled or bool(
                                cancel_payload.get("task_cancelled", False)
                            )
                            queue_cancelled_count += max(
                                0,
                                int(cancel_payload.get("queue_cancelled_count", 0)),
                            )
                    except Exception as exc:
                        print(
                            f"[case-delete][{normalized_case_id}] process_control_cancel_failed "
                            f"error={exc}"
                        )

                with index_lock:
                    job = index_jobs.get(normalized_case_id)
                    if isinstance(job, dict):
                        status = str(job.get("status") or "").strip().lower()
                        if bool(job.get("running")) or status in {
                            "queued",
                            "running",
                            "cancelling",
                            "deleting",
                        }:
                            job["cancel_requested"] = True
                            job["status"] = "cancelling"
                            job["running"] = False
                            cancel_requested = True
                    task = index_tasks.get(normalized_case_id)
                    if isinstance(task, asyncio.Task) and not task.done():
                        task.cancel()
                        task_cancelled = True
                        cancel_requested = True

                if index_queue_store is not None and hasattr(index_queue_store, "cancel_case_active"):
                    try:
                        queue_cancelled = await asyncio.to_thread(
                            index_queue_store.cancel_case_active,
                            normalized_case_id,
                            reason=reason,
                        )
                        queue_cancelled = max(0, int(queue_cancelled))
                        queue_cancelled_count += queue_cancelled
                        if queue_cancelled > 0:
                            cancel_requested = True
                    except Exception as exc:
                        print(
                            f"[case-delete][{normalized_case_id}] queue_cancel_failed error={exc}"
                        )

            quiescence_timeout_seconds = max(0.5, float(delete_quiescence_timeout_seconds))
            poll_interval_seconds = max(0.05, float(delete_poll_interval_seconds))
            required_quiet_polls = max(1, int(delete_required_quiet_polls))
            quiet_polls = 0
            loop = asyncio.get_running_loop()
            wait_deadline = loop.time() + quiescence_timeout_seconds
            cancel_reason = "Cancelled because case deletion was requested."

            while True:
                await _request_case_stop(reason=cancel_reason)
                active, _ = await _case_has_active_index_processes()

                if not active and index_queue_store is not None and hasattr(index_queue_store, "clear_case"):
                    try:
                        await asyncio.to_thread(index_queue_store.clear_case, normalized_case_id)
                    except Exception as exc:
                        print(
                            f"[index-queue][{normalized_case_id}] clear_case_before_delete_failed "
                            f"error={exc}"
                        )
                    active, _ = await _case_has_active_index_processes()

                if active:
                    quiet_polls = 0
                else:
                    quiet_polls += 1
                    if quiet_polls >= required_quiet_polls:
                        break

                if loop.time() >= wait_deadline:
                    break
                await asyncio.sleep(poll_interval_seconds)

            await _request_case_stop(reason=cancel_reason)
            if index_queue_store is not None and hasattr(index_queue_store, "clear_case"):
                try:
                    await asyncio.to_thread(index_queue_store.clear_case, normalized_case_id)
                except Exception as exc:
                    print(
                        f"[index-queue][{normalized_case_id}] final_clear_case_before_delete_failed "
                        f"error={exc}"
                    )

            still_active, active_filename = await _case_has_active_index_processes()
            if still_active:
                active_hint = f" (current file: {active_filename})" if active_filename else ""
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Case {normalized_case_id} is still busy with background processing{active_hint}. "
                        "Deletion was not performed; retry in a short while."
                    ),
                )

            deleted: dict | None = None
            delete_attempts = 6
            last_permission_error: Exception | None = None
            for attempt in range(delete_attempts):
                try:
                    deleted = await asyncio.to_thread(delete_case_sync, normalized_case_id)
                    break
                except PermissionError as exc:
                    last_permission_error = exc
                    if attempt >= delete_attempts - 1:
                        break
                    await asyncio.sleep(0.45 * float(attempt + 1))

            if deleted is None:
                if last_permission_error is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Case files are still in use for {normalized_case_id}. "
                            "Playback or background processing may still be releasing file handles. "
                            f"Please retry deletion shortly. Detail: {last_permission_error}"
                        ),
                    )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete case: {normalized_case_id}",
                )

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

            if index_queue_store is not None:
                try:
                    await asyncio.to_thread(index_queue_store.clear_case, deleted["case_id"])
                except Exception as exc:
                    print(
                        f"[index-queue][{deleted['case_id']}] clear_case_failed error={exc}"
                    )

            video_pipeline_store = getattr(request.app.state, "video_pipeline_store", None)
            if video_pipeline_store is not None:
                try:
                    await asyncio.to_thread(
                        video_pipeline_store.delete_case,
                        deleted["case_id"],
                    )
                except Exception as exc:
                    print(
                        f"[pipeline][{deleted['case_id']}] delete_case_failed error={exc}"
                    )

            triage_timeline_store = getattr(request.app.state, "triage_timeline_store", None)
            if triage_timeline_store is not None and hasattr(triage_timeline_store, "delete_case"):
                try:
                    await asyncio.to_thread(
                        triage_timeline_store.delete_case,
                        deleted["case_id"],
                    )
                except Exception as exc:
                    print(
                        f"[triage-cache][{deleted['case_id']}] delete_case_failed error={exc}"
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
                "cancel_requested": bool(cancel_requested),
                "queue_cancelled_count": int(max(0, queue_cancelled_count)),
                "task_cancelled": bool(task_cancelled),
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
        finally:
            if (
                guard_acquired
                and guard_lock is not None
                and hasattr(guard_lock, "acquire")
                and isinstance(deleting_cases, set)
                and normalized_case_id
            ):
                with guard_lock:
                    deleting_cases.discard(normalized_case_id)

    return router
