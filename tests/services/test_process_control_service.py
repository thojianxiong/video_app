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
                self.delete_calls: list[tuple[tuple[int, ...], bool]] = []
                self.cancel_calls: list[tuple[tuple[int, ...], bool]] = []
                self.prioritize_calls: list[tuple[int, tuple[str, ...]]] = []
                self.jobs: dict[int, dict] = {
                    99: {
                        "job_id": 99,
                        "case_id": "case_done",
                        "job_kind": "semantic_index",
                        "status": "queued",
                        "priority": 50,
                        "attempt_count": 0,
                        "enqueued_at": "2026-01-01T00:00:00+00:00",
                        "started_at": "",
                        "updated_at": "2026-01-01T00:01:00+00:00",
                        "payload": {"filenames": ["drop.mp4", "keep.mp4"]},
                    },
                    101: {
                        "job_id": 101,
                        "case_id": "case_running",
                        "job_kind": "semantic_index",
                        "status": "running",
                        "priority": 50,
                        "attempt_count": 1,
                        "enqueued_at": "2026-01-01T00:00:00+00:00",
                        "started_at": "2026-01-01T00:00:10+00:00",
                        "updated_at": "2026-01-01T00:01:00+00:00",
                        "payload": {"filenames": ["video1.mp4"]},
                    },
                }

            def cancel_case_active(
                self,
                case_id: str,
                *,
                reason: str = "",
                job_kind: str | None = None,
            ) -> int:
                self.calls.append((str(case_id), str(reason)))
                return 1 if str(case_id) == "case_running" else 0

            def get_job(self, job_id: int) -> dict | None:
                job = self.jobs.get(int(job_id))
                return dict(job) if isinstance(job, dict) else None

            def delete_jobs(
                self,
                *,
                job_ids: list[int],
                cancel_running: bool = False,
                reason: str = "",
            ) -> dict:
                parsed_ids = tuple(int(item) for item in job_ids)
                self.delete_calls.append((parsed_ids, bool(cancel_running)))
                removed_ids = [item for item in parsed_ids if item in self.jobs and self.jobs[item].get("status") != "running"]
                skipped_running_ids = [item for item in parsed_ids if item in self.jobs and self.jobs[item].get("status") == "running"]
                for item in removed_ids:
                    self.jobs.pop(item, None)
                return {
                    "requested_count": len(parsed_ids),
                    "found_count": len([item for item in parsed_ids if item in self.jobs or item in removed_ids]),
                    "removed_count": len(removed_ids),
                    "cancelled_running_count": 0,
                    "skipped_running_count": len(skipped_running_ids),
                    "removed_job_ids": removed_ids,
                    "cancelled_running_job_ids": [],
                    "skipped_running_job_ids": skipped_running_ids,
                    "not_found_ids": [],
                    "affected_case_ids": ["case_done"] if removed_ids else [],
                }

            def cancel_jobs(
                self,
                *,
                job_ids: list[int],
                include_running: bool = True,
                reason: str = "",
            ) -> dict:
                parsed_ids = tuple(int(item) for item in job_ids)
                self.cancel_calls.append((parsed_ids, bool(include_running)))
                cancelled_ids = []
                for item in parsed_ids:
                    job = self.jobs.get(item)
                    if not isinstance(job, dict):
                        continue
                    if str(job.get("status")) in {"queued", "running"}:
                        job["status"] = "cancelled"
                        cancelled_ids.append(item)
                return {
                    "requested_count": len(parsed_ids),
                    "found_count": len([item for item in parsed_ids if item in self.jobs or item in cancelled_ids]),
                    "cancelled_count": len(cancelled_ids),
                    "cancelled_job_ids": cancelled_ids,
                    "skipped_running_count": 0,
                    "skipped_running_job_ids": [],
                    "terminal_count": 0,
                    "terminal_job_ids": [],
                    "not_found_ids": [],
                    "affected_case_ids": ["case_running"] if cancelled_ids else [],
                }

            def prioritize_job(
                self,
                *,
                job_id: int,
                priority: int = 1,
                filenames_front: list[str] | tuple[str, ...] | set[str] | None = None,
            ) -> dict:
                parsed_job_id = int(job_id)
                selected = tuple(str(item) for item in (filenames_front or []))
                self.prioritize_calls.append((parsed_job_id, selected))
                job = self.jobs.get(parsed_job_id)
                if not isinstance(job, dict):
                    return {"job_id": parsed_job_id, "found": False, "updated": False}
                if str(job.get("status")) != "queued":
                    return {"job_id": parsed_job_id, "found": True, "updated": False, "blocked_status": str(job.get("status"))}
                job["priority"] = int(priority)
                return {
                    "job_id": parsed_job_id,
                    "found": True,
                    "updated": True,
                    "front_applied_count": len(selected),
                    "front_applied_filenames": list(selected),
                    "front_missing_filenames": [],
                    "job": {
                        "job_id": parsed_job_id,
                        "job_kind": str(job.get("job_kind", "")),
                        "priority": int(job.get("priority", 0)),
                        "status": str(job.get("status", "")),
                        "queue_position": 0,
                        "attempt_count": int(job.get("attempt_count", 0)),
                        "enqueued_at": str(job.get("enqueued_at", "")),
                        "started_at": str(job.get("started_at", "")),
                        "updated_at": str(job.get("updated_at", "")),
                    },
                    "message": "Queue job moved to front.",
                }

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
            case_id="case_done",
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

    def test_delete_queue_jobs_sync_is_case_scoped(self) -> None:
        payload = self.service.delete_queue_jobs_sync(
            case_id="case_done",
            job_ids=[99, 101],
            cancel_running=False,
        )
        self.assertEqual(payload["removed_count"], 1)
        self.assertEqual(payload["wrong_case_job_ids"], [101])
        self.assertEqual(len(self.app.state.index_queue_store.delete_calls), 1)

    def test_stop_queue_jobs_sync_requests_cancel(self) -> None:
        payload = self.service.stop_queue_jobs_sync(
            case_id="case_running",
            job_ids=[101],
        )
        self.assertEqual(payload["cancelled_count"], 1)
        self.assertEqual(len(self.app.state.index_queue_store.cancel_calls), 1)

    def test_run_queue_job_sync_moves_job_to_front(self) -> None:
        payload = self.service.run_queue_job_sync(
            case_id="case_done",
            job_id=99,
            filenames=["drop.mp4"],
        )
        self.assertTrue(payload["updated"])
        self.assertEqual(payload["front_applied_count"], 1)

    def test_list_active_processes_sync_collapses_completed_submission_items(self) -> None:
        queue_store = self.app.state.index_queue_store
        queue_store.list_active_jobs = lambda limit=500: []
        queue_store.list_recent_jobs = lambda limit=500: [
            {
                "job_id": 201,
                "case_id": "case_done",
                "job_kind": "analysis",
                "priority": 70,
                "status": "completed",
                "attempt_count": 1,
                "queue_position": 0,
                "enqueued_at": "2026-01-01T00:00:00+00:00",
                "started_at": "2026-01-01T00:00:10+00:00",
                "finished_at": "2026-01-01T00:01:00+00:00",
                "updated_at": "2026-01-01T00:01:00+00:00",
                "payload": {
                    "filenames": ["a.mp4"],
                    "metadata": {
                        "analysis_face_people": True,
                        "analysis_face_people_filenames": ["a.mp4"],
                        "submission_id": "sub-1",
                        "submission_created_at": "2026-01-01T00:00:00+00:00",
                        "submission_kind": "analysis",
                    },
                },
            },
            {
                "job_id": 202,
                "case_id": "case_done",
                "job_kind": "analysis",
                "priority": 70,
                "status": "failed",
                "attempt_count": 1,
                "queue_position": 0,
                "enqueued_at": "2026-01-01T00:01:05+00:00",
                "started_at": "2026-01-01T00:01:15+00:00",
                "finished_at": "2026-01-01T00:02:00+00:00",
                "updated_at": "2026-01-01T00:02:00+00:00",
                "payload": {
                    "filenames": ["b.mp4"],
                    "metadata": {
                        "analysis_vehicles": True,
                        "analysis_vehicles_filenames": ["b.mp4"],
                        "submission_id": "sub-1",
                        "submission_created_at": "2026-01-01T00:00:00+00:00",
                        "submission_kind": "analysis",
                    },
                },
            },
        ]

        payload = self.service.list_active_processes_sync(case_id="case_done")
        completed = payload["completed_processes"]
        self.assertEqual(payload["completed_count"], 1)
        self.assertEqual(len(completed), 1)
        item = completed[0]
        self.assertEqual(item["submission_id"], "sub-1")
        self.assertEqual(item["submission_kind"], "analysis")
        self.assertEqual(item["status"], "completed_with_errors")
        self.assertEqual(item["filenames_count"], 2)
        self.assertEqual(sorted(item["filenames"]), ["a.mp4", "b.mp4"])
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        self.assertTrue(bool(metadata.get("analysis_face_people")))
        self.assertTrue(bool(metadata.get("analysis_vehicles")))

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
