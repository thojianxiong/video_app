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
                self.remove_calls: list[tuple[int, tuple[str, ...]]] = []

            def cancel_case_active(self, case_id: str, *, reason: str = "") -> int:
                self.calls.append((str(case_id), str(reason)))
                return 1 if str(case_id) == "case_running" else 0

            def remove_files_from_job(
                self,
                *,
                job_id: int,
                filenames: list[str],
                allow_running: bool = False,
                reason: str = "",
            ) -> dict:
                self.remove_calls.append((int(job_id), tuple(str(item) for item in filenames)))
                if int(job_id) == 404:
                    return {
                        "job_id": int(job_id),
                        "found": False,
                        "removed_count": 0,
                        "remaining_count": 0,
                        "removed_filenames": [],
                        "remaining_filenames": [],
                        "not_found_filenames": list(filenames),
                        "deleted_job": False,
                        "blocked_running": False,
                    }
                return {
                    "job_id": int(job_id),
                    "found": True,
                    "case_id": "case_done",
                    "job_kind": "semantic_index",
                    "status": "queued",
                    "removed_count": 1,
                    "remaining_count": 1,
                    "removed_filenames": [str(filenames[0])],
                    "remaining_filenames": ["keep.mp4"],
                    "not_found_filenames": [],
                    "deleted_job": False,
                    "blocked_running": False,
                    "job": {
                        "job_id": int(job_id),
                        "job_kind": "semantic_index",
                        "priority": 50,
                        "status": "queued",
                        "queue_position": 0,
                        "attempt_count": 0,
                        "enqueued_at": "2026-01-01T00:00:00+00:00",
                        "started_at": "",
                        "updated_at": "2026-01-01T00:01:00+00:00",
                    },
                }

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

    def test_remove_queue_job_files_sync_updates_semantic_snapshot(self) -> None:
        payload = self.service.remove_queue_job_files_sync(
            job_id=99,
            filenames=["drop.mp4"],
        )
        self.assertEqual(payload["removed_count"], 1)
        self.assertEqual(payload["remaining_filenames"], ["keep.mp4"])
        updated = self.app.state.index_jobs["case_done"]
        self.assertEqual(updated["status"], "queued")
        self.assertEqual(updated["filenames"], ["keep.mp4"])
        self.assertEqual(updated["total"], 1)
        self.assertEqual(len(self.app.state.index_queue_store.remove_calls), 1)

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
