from __future__ import annotations

import asyncio
import os
import signal
from threading import Lock
from typing import Any


class ProcessControlService:
    def __init__(
        self,
        *,
        app: Any,
        utc_now_iso: Any,
        index_job_snapshot: Any,
    ) -> None:
        self.app = app
        self.utc_now_iso = utc_now_iso
        self.index_job_snapshot = index_job_snapshot

    @staticmethod
    def _is_active_job(job: dict) -> bool:
        status = str(job.get("status") or "")
        return bool(job.get("running")) or status in {"queued", "running", "cancelling"}

    @staticmethod
    def _normalize_filenames(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        output: list[str] = []
        seen: set[str] = set()
        for raw in value:
            safe = str(raw or "").strip()
            if not safe or safe in seen:
                continue
            seen.add(safe)
            output.append(safe)
        return output

    @staticmethod
    def _safe_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)

    @staticmethod
    def _safe_float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    @staticmethod
    def _normalize_stage_status(value: Any, fallback: str = "pending") -> str:
        normalized = str(value or "").strip().lower()
        if normalized:
            return normalized
        return str(fallback or "pending").strip().lower() or "pending"

    @staticmethod
    def _stage_name_for_job_kind(job_kind: str) -> str:
        normalized = str(job_kind or "").strip().lower()
        if normalized == "semantic_index":
            return "base_index"
        if normalized == "analysis":
            return "analysis"
        if normalized == "triage_timeline":
            return "triage"
        return ""

    def _load_case_pipeline_snapshots_map(
        self,
        *,
        case_id: str,
        cache: dict[str, dict[str, dict]],
    ) -> dict[str, dict]:
        safe_case_id = str(case_id or "").strip()
        if not safe_case_id:
            return {}
        cached = cache.get(safe_case_id)
        if isinstance(cached, dict):
            return cached

        store = getattr(self.app.state, "video_pipeline_store", None)
        mapping: dict[str, dict] = {}
        if store is None or not hasattr(store, "list_case_snapshots"):
            cache[safe_case_id] = mapping
            return mapping

        try:
            snapshots = store.list_case_snapshots(safe_case_id)
        except Exception:
            snapshots = []
        for item in snapshots:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename") or "").strip()
            if not filename:
                continue
            mapping[filename] = item
        cache[safe_case_id] = mapping
        return mapping

    def _build_file_progress_rows(
        self,
        *,
        case_id: str,
        filenames: list[str],
        stage_name: str,
        fallback_status: str,
        snapshot_cache: dict[str, dict[str, dict]],
        current_filename: str = "",
        current_processed_frames: int = 0,
        current_total_frames: int = 0,
        current_progress_percent: float = 0.0,
    ) -> list[dict]:
        safe_filenames = self._normalize_filenames(filenames)
        if not safe_filenames:
            return []

        stage = str(stage_name or "").strip()
        default_status = self._normalize_stage_status(fallback_status, fallback="pending")
        safe_current_filename = str(current_filename or "").strip()
        safe_current_processed = max(0, self._safe_int(current_processed_frames))
        safe_current_total = max(0, self._safe_int(current_total_frames))
        safe_current_percent = min(100.0, max(0.0, self._safe_float(current_progress_percent)))
        snapshots_by_filename = self._load_case_pipeline_snapshots_map(
            case_id=case_id,
            cache=snapshot_cache,
        )

        rows: list[dict] = []
        for filename in safe_filenames:
            snapshot = snapshots_by_filename.get(filename)
            stage_payload = None
            if (
                isinstance(snapshot, dict)
                and isinstance(snapshot.get("stages"), dict)
                and stage
                and isinstance(snapshot["stages"].get(stage), dict)
            ):
                stage_payload = snapshot["stages"][stage]

            status = self._normalize_stage_status(
                stage_payload.get("status") if isinstance(stage_payload, dict) else "",
                fallback=default_status,
            )
            details = (
                stage_payload.get("details")
                if isinstance(stage_payload, dict) and isinstance(stage_payload.get("details"), dict)
                else {}
            )

            processed = max(0, self._safe_int(details.get("processed_frames", 0)))
            total = max(
                0,
                self._safe_int(
                    details.get("estimated_total_frames", details.get("total_frames", 0)),
                ),
            )
            if total > 0 and total < processed:
                total = processed

            percent = self._safe_float(details.get("progress_percent"), fallback=0.0)
            if total > 0:
                percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
            else:
                percent = min(100.0, max(0.0, percent))

            is_current = bool(safe_current_filename) and filename == safe_current_filename
            if is_current:
                if safe_current_processed > processed:
                    processed = safe_current_processed
                if safe_current_total > total:
                    total = safe_current_total
                if total > 0 and total < processed:
                    total = processed
                if total > 0:
                    percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
                else:
                    percent = max(percent, safe_current_percent)

            if status in {"completed", "skipped", "failed", "interrupted"}:
                percent = 100.0
            elif status == "running":
                if total > 0:
                    percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
                elif is_current and safe_current_percent > 0:
                    percent = min(100.0, max(0.0, safe_current_percent))

            rows.append(
                {
                    "filename": filename,
                    "status": status,
                    "processed_frames": int(processed),
                    "estimated_total_frames": int(total),
                    "progress_percent": float(min(100.0, max(0.0, percent))),
                    "is_current": bool(is_current),
                }
            )
        return rows

    def list_active_processes_sync(self) -> dict:
        jobs: dict[str, dict] = self.app.state.index_jobs
        lock: Lock = self.app.state.index_jobs_lock
        processes: list[dict] = []
        pipeline_snapshot_cache: dict[str, dict[str, dict]] = {}

        with lock:
            for raw_case_id, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                case_id = str(raw_case_id or "").strip()
                if not case_id:
                    continue
                status = str(job.get("status") or "")
                if not self._is_active_job(job):
                    continue
                snapshot = self.index_job_snapshot(job, case_id=case_id)
                snapshot_filenames = [
                    str(name).strip()
                    for name in (snapshot.get("filenames") or [])
                    if str(name).strip()
                ]
                current_filename = str(snapshot.get("current_filename") or "")
                current_video_processed_frames = max(
                    0,
                    self._safe_int(snapshot.get("current_video_processed_frames", 0)),
                )
                current_video_total_frames = max(
                    0,
                    self._safe_int(snapshot.get("current_video_total_frames", 0)),
                )
                current_video_progress_percent = min(
                    100.0,
                    max(0.0, self._safe_float(snapshot.get("current_video_progress_percent", 0.0))),
                )
                file_progress = self._build_file_progress_rows(
                    case_id=case_id,
                    filenames=snapshot_filenames,
                    stage_name="base_index",
                    fallback_status=str(snapshot.get("status", status)),
                    snapshot_cache=pipeline_snapshot_cache,
                    current_filename=current_filename,
                    current_processed_frames=current_video_processed_frames,
                    current_total_frames=current_video_total_frames,
                    current_progress_percent=current_video_progress_percent,
                )
                processes.append(
                    {
                        "type": "background_index",
                        "case_id": case_id,
                        "status": snapshot.get("status", status),
                        "current_filename": current_filename,
                        "completed": int(snapshot.get("completed", 0)),
                        "total": int(snapshot.get("total", 0)),
                        "progress_percent": float(snapshot.get("progress_percent", 0.0)),
                        "current_video_processed_frames": current_video_processed_frames,
                        "current_video_total_frames": current_video_total_frames,
                        "current_video_progress_percent": current_video_progress_percent,
                        "started_at": snapshot.get("started_at", ""),
                        "updated_at": snapshot.get("updated_at", ""),
                        "filenames_count": len(snapshot_filenames),
                        "filenames_preview": snapshot_filenames[:5],
                        "filenames": snapshot_filenames,
                        "file_progress": file_progress,
                    }
                )

        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is not None and hasattr(queue_store, "list_active_jobs"):
            try:
                active_queue_jobs = queue_store.list_active_jobs(limit=500)
            except Exception:
                active_queue_jobs = []
            for item in active_queue_jobs:
                if not isinstance(item, dict):
                    continue
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                filenames = [
                    str(name).strip()
                    for name in (payload.get("filenames") or [])
                    if str(name).strip()
                ]
                metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
                face_people_filenames = [
                    str(name).strip()
                    for name in (metadata.get("analysis_face_people_filenames") or [])
                    if str(name).strip()
                ]
                vehicles_filenames = [
                    str(name).strip()
                    for name in (metadata.get("analysis_vehicles_filenames") or [])
                    if str(name).strip()
                ]
                case_id = str(item.get("case_id") or "")
                status = str(item.get("status") or "")
                job_kind = str(item.get("job_kind") or "")
                file_progress = self._build_file_progress_rows(
                    case_id=case_id,
                    filenames=filenames,
                    stage_name=self._stage_name_for_job_kind(job_kind),
                    fallback_status=status,
                    snapshot_cache=pipeline_snapshot_cache,
                )
                processes.append(
                    {
                        "type": "queue_job",
                        "queue_job_id": int(item.get("job_id", 0)),
                        "job_kind": job_kind,
                        "priority": int(item.get("priority", 0)),
                        "case_id": case_id,
                        "status": status,
                        "queue_position": max(0, int(item.get("queue_position", 0))),
                        "attempt_count": int(item.get("attempt_count", 0)),
                        "filenames_count": len(filenames),
                        "filenames_preview": filenames[:5],
                        "filenames": filenames,
                        "file_progress": file_progress,
                        "metadata": {
                            "analysis_face_people": bool(metadata.get("analysis_face_people", False)),
                            "analysis_vehicles": bool(metadata.get("analysis_vehicles", False)),
                            "analysis_only": bool(metadata.get("analysis_only", False)),
                            "analysis_face_people_filenames": face_people_filenames,
                            "analysis_vehicles_filenames": vehicles_filenames,
                        },
                        "enqueued_at": str(item.get("enqueued_at") or ""),
                        "started_at": str(item.get("started_at") or ""),
                        "updated_at": str(item.get("updated_at") or ""),
                    }
                )

        return {
            "shutdown_requested": bool(getattr(self.app.state, "shutdown_requested", False)),
            "shutdown_requested_at": str(getattr(self.app.state, "shutdown_requested_at", "") or ""),
            "count": len(processes),
            "processes": processes,
        }

    def cancel_running_index_jobs_sync(self) -> dict:
        jobs: dict[str, dict] = self.app.state.index_jobs
        tasks: dict[str, asyncio.Task] = self.app.state.index_tasks
        lock: Lock = self.app.state.index_jobs_lock
        cancelled_case_ids: set[str] = set()
        now = self.utc_now_iso()

        with lock:
            for raw_case_id, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                case_id = str(raw_case_id or "").strip()
                if not case_id:
                    continue
                if not self._is_active_job(job):
                    continue
                job["cancel_requested"] = True
                job["status"] = "cancelling"
                job["running"] = False
                job["updated_at"] = now
                cancelled_case_ids.add(case_id)

            for raw_case_id, task in list(tasks.items()):
                case_id = str(raw_case_id or "").strip()
                if not case_id or not isinstance(task, asyncio.Task):
                    continue
                if task.done():
                    continue
                task.cancel()
                cancelled_case_ids.add(case_id)
                job = jobs.get(case_id)
                if isinstance(job, dict):
                    job["cancel_requested"] = True
                    job["status"] = "cancelling"
                    job["running"] = False
                    job["updated_at"] = now

        return {
            "cancelled_count": len(cancelled_case_ids),
            "cancelled_case_ids": sorted(cancelled_case_ids),
        }

    def cancel_case_index_jobs_sync(
        self,
        *,
        case_id: str,
        force: bool = False,
        reason: str = "Cancelled by user request.",
    ) -> dict:
        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            raise ValueError("case_id is required")

        jobs: dict[str, dict] = self.app.state.index_jobs
        tasks: dict[str, asyncio.Task] = self.app.state.index_tasks
        lock: Lock = self.app.state.index_jobs_lock
        now = self.utc_now_iso()

        requested = False
        task_cancelled = False

        with lock:
            job = jobs.get(normalized_case_id)
            if isinstance(job, dict) and self._is_active_job(job):
                job["cancel_requested"] = True
                job["status"] = "cancelling"
                job["running"] = False
                job["updated_at"] = now
                requested = True

            task = tasks.get(normalized_case_id)
            if force and isinstance(task, asyncio.Task) and not task.done():
                task.cancel()
                task_cancelled = True
                requested = True
                if isinstance(job, dict):
                    job["cancel_requested"] = True
                    job["status"] = "cancelling"
                    job["running"] = False
                    job["updated_at"] = now

        queue_cancelled = 0
        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is not None:
            try:
                queue_cancelled = int(
                    queue_store.cancel_case_active(
                        normalized_case_id,
                        reason=str(reason or "").strip() or "Cancelled by user request.",
                    )
                )
                if queue_cancelled > 0:
                    requested = True
            except Exception as exc:
                print(f"[index-queue][{normalized_case_id}] cancel_case_active_failed error={exc}")

        active_after_cancel = False
        with lock:
            remaining = jobs.get(normalized_case_id)
            if isinstance(remaining, dict):
                active_after_cancel = self._is_active_job(remaining)

        return {
            "case_id": normalized_case_id,
            "cancel_requested": bool(requested),
            "task_cancelled": bool(task_cancelled),
            "queue_cancelled_count": max(0, int(queue_cancelled)),
            "active_after_cancel": bool(active_after_cancel),
            "message": (
                "Cancellation requested."
                if requested
                else "No active semantic indexing process found for this case."
            ),
        }

    def schedule_process_exit(self, delay_seconds: float = 1.0) -> None:
        loop = asyncio.get_running_loop()

        def _trigger_exit() -> None:
            try:
                signal.raise_signal(signal.SIGINT)
            except Exception:
                os._exit(0)

        loop.call_later(max(0.2, float(delay_seconds)), _trigger_exit)

    async def list_processes(self) -> dict:
        return await asyncio.to_thread(self.list_active_processes_sync)

    async def cancel_case_index_jobs(
        self,
        *,
        case_id: str,
        force: bool = False,
        reason: str = "Cancelled by user request.",
    ) -> dict:
        return await asyncio.to_thread(
            self.cancel_case_index_jobs_sync,
            case_id=case_id,
            force=force,
            reason=reason,
        )

    def delete_queue_jobs_sync(
        self,
        *,
        job_ids: list[int],
        cancel_running: bool = True,
    ) -> dict:
        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is None or not hasattr(queue_store, "delete_jobs"):
            raise ValueError("Queue store is unavailable.")

        result = queue_store.delete_jobs(
            job_ids=job_ids,
            cancel_running=bool(cancel_running),
            reason="Removed from queue by user request.",
        )
        if not isinstance(result, dict):
            result = {}

        affected_case_ids = [
            str(item).strip()
            for item in (result.get("affected_case_ids") or [])
            if str(item).strip()
        ]
        if affected_case_ids:
            jobs: dict[str, dict] = self.app.state.index_jobs
            lock: Lock = self.app.state.index_jobs_lock
            now = self.utc_now_iso()
            with lock:
                for case_id in affected_case_ids:
                    job = jobs.get(case_id)
                    if not isinstance(job, dict):
                        continue
                    status = str(job.get("status") or "").strip().lower()
                    running = bool(job.get("running"))
                    if running:
                        continue
                    if status in {"queued", "cancelling"}:
                        job["status"] = "idle"
                        job["running"] = False
                        job["cancel_requested"] = False
                        job["queue_job_id"] = 0
                        job["queue_job_kind"] = ""
                        job["queue_priority"] = 0
                        job["updated_at"] = now

        return {
            "requested_count": int(result.get("requested_count", 0)),
            "found_count": int(result.get("found_count", 0)),
            "removed_count": int(result.get("removed_count", 0)),
            "cancelled_running_count": int(result.get("cancelled_running_count", 0)),
            "skipped_running_count": int(result.get("skipped_running_count", 0)),
            "removed_job_ids": result.get("removed_job_ids") or [],
            "cancelled_running_job_ids": result.get("cancelled_running_job_ids") or [],
            "skipped_running_job_ids": result.get("skipped_running_job_ids") or [],
            "not_found_ids": result.get("not_found_ids") or [],
            "affected_case_ids": affected_case_ids,
            "message": "Queue items updated.",
        }

    async def delete_queue_jobs(
        self,
        *,
        job_ids: list[int],
        cancel_running: bool = True,
    ) -> dict:
        return await asyncio.to_thread(
            self.delete_queue_jobs_sync,
            job_ids=job_ids,
            cancel_running=cancel_running,
        )

    async def graceful_shutdown(self, *, confirm: bool) -> dict:
        if not confirm:
            raise ValueError("confirm=true is required for shutdown.")

        process_snapshot = await asyncio.to_thread(self.list_active_processes_sync)
        cancel_payload = await asyncio.to_thread(self.cancel_running_index_jobs_sync)
        self.app.state.shutdown_requested = True
        self.app.state.shutdown_requested_at = self.utc_now_iso()
        self.schedule_process_exit(1.0)

        return {
            "accepted": True,
            "message": "Graceful shutdown scheduled.",
            "active_process_count": int(process_snapshot.get("count", 0)),
            "active_processes": process_snapshot.get("processes", []),
            "cancelled_count": int(cancel_payload.get("cancelled_count", 0)),
            "cancelled_case_ids": cancel_payload.get("cancelled_case_ids", []),
            "shutdown_requested_at": str(self.app.state.shutdown_requested_at),
        }
