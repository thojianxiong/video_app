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

    def list_active_processes_sync(self) -> dict:
        jobs: dict[str, dict] = self.app.state.index_jobs
        lock: Lock = self.app.state.index_jobs_lock
        processes: list[dict] = []

        with lock:
            for raw_case_id, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                case_id = str(raw_case_id or "").strip()
                if not case_id:
                    continue
                status = str(job.get("status") or "")
                running = bool(job.get("running")) or status in {"queued", "running", "cancelling"}
                if not running:
                    continue
                snapshot = self.index_job_snapshot(job, case_id=case_id)
                processes.append(
                    {
                        "type": "background_index",
                        "case_id": case_id,
                        "status": snapshot.get("status", status),
                        "current_filename": snapshot.get("current_filename", ""),
                        "completed": int(snapshot.get("completed", 0)),
                        "total": int(snapshot.get("total", 0)),
                        "progress_percent": float(snapshot.get("progress_percent", 0.0)),
                        "started_at": snapshot.get("started_at", ""),
                        "updated_at": snapshot.get("updated_at", ""),
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
                status = str(job.get("status") or "")
                running = bool(job.get("running")) or status in {"queued", "running", "cancelling"}
                if not running:
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
