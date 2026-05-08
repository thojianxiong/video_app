from __future__ import annotations

import unittest
from types import SimpleNamespace
from threading import Lock

from backend.services.process_control_service import ProcessControlService


def _snapshot(job: dict | None, *, case_id: str) -> dict:
    payload = dict(job or {})
    payload.setdefault("status", "idle")
    payload.setdefault("current_filename", "")
    payload.setdefault("completed", 0)
    payload.setdefault("total", 0)
    payload.setdefault("progress_percent", 0.0)
    payload.setdefault("started_at", "")
    payload.setdefault("updated_at", "")
    payload["case_id"] = case_id
    return payload


class ProcessControlServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        class _FakeQueueStore:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def cancel_case_active(self, case_id: str, *, reason: str = "") -> int:
                self.calls.append((str(case_id), str(reason)))
                return 1 if str(case_id) == "case_running" else 0

        state = SimpleNamespace()
        state.index_jobs = {
            "case_running": {
                "status": "running",
                "running": True,
                "current_filename": "video1.mp4",
                "completed": 1,
                "total": 3,
                "progress_percent": 33.3,
                "started_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:01:00+00:00",
            },
            "case_done": {
                "status": "completed",
                "running": False,
                "completed": 2,
                "total": 2,
                "progress_percent": 100.0,
            },
        }
        state.index_jobs_lock = Lock()
        state.index_tasks = {}
        state.index_queue_store = _FakeQueueStore()
        state.shutdown_requested = False
        state.shutdown_requested_at = ""

        self.app = SimpleNamespace(state=state)
        self.service = ProcessControlService(
            app=self.app,
            utc_now_iso=lambda: "2026-05-07T00:00:00+00:00",
            index_job_snapshot=_snapshot,
        )

    def test_list_active_processes_sync_returns_running_only(self) -> None:
        payload = self.service.list_active_processes_sync()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["processes"]), 1)
        process = payload["processes"][0]
        self.assertEqual(process["case_id"], "case_running")
        self.assertEqual(process["status"], "running")
        self.assertEqual(process["current_filename"], "video1.mp4")

    def test_cancel_running_index_jobs_sync_marks_jobs(self) -> None:
        payload = self.service.cancel_running_index_jobs_sync()
        self.assertEqual(payload["cancelled_count"], 1)
        self.assertEqual(payload["cancelled_case_ids"], ["case_running"])
        running_job = self.app.state.index_jobs["case_running"]
        self.assertTrue(running_job["cancel_requested"])
        self.assertEqual(running_job["status"], "cancelling")
        self.assertFalse(running_job["running"])

    def test_cancel_case_index_jobs_sync_marks_target_case(self) -> None:
        payload = self.service.cancel_case_index_jobs_sync(case_id="case_running")
        self.assertTrue(payload["cancel_requested"])
        self.assertEqual(payload["case_id"], "case_running")
        self.assertEqual(payload["queue_cancelled_count"], 1)
        running_job = self.app.state.index_jobs["case_running"]
        self.assertTrue(running_job["cancel_requested"])
        self.assertEqual(running_job["status"], "cancelling")
        self.assertFalse(running_job["running"])
        self.assertEqual(len(self.app.state.index_queue_store.calls), 1)

    def test_cancel_case_index_jobs_sync_requires_case_id(self) -> None:
        with self.assertRaises(ValueError):
            self.service.cancel_case_index_jobs_sync(case_id="  ")

    async def test_graceful_shutdown_sets_state(self) -> None:
        # Prevent signal-based exit scheduling during test runs.
        self.service.schedule_process_exit = lambda _delay_seconds=1.0: None

        payload = await self.service.graceful_shutdown(confirm=True)
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["cancelled_count"], 1)
        self.assertTrue(self.app.state.shutdown_requested)
        self.assertEqual(
            self.app.state.shutdown_requested_at,
            "2026-05-07T00:00:00+00:00",
        )

    async def test_graceful_shutdown_requires_confirm(self) -> None:
        with self.assertRaises(ValueError):
            await self.service.graceful_shutdown(confirm=False)


if __name__ == "__main__":
    unittest.main()
