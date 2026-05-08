from __future__ import annotations

import unittest
from threading import Lock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.cases import build_cases_router


class _BusyQueueStore:
    def __init__(self) -> None:
        self.cancel_calls = 0
        self.clear_calls = 0

    def get_case_active(self, case_id: str) -> dict:
        return {
            "case_id": str(case_id),
            "status": "running",
            "payload": {"filenames": ["busy.mp4"]},
        }

    def cancel_case_active(self, case_id: str, *, reason: str = "") -> int:
        self.cancel_calls += 1
        return 0

    def clear_case(self, case_id: str) -> None:
        self.clear_calls += 1


class _TransitionQueueStore:
    def __init__(self) -> None:
        self.active = True
        self.cancel_calls = 0
        self.clear_calls = 0

    def get_case_active(self, case_id: str) -> dict | None:
        if not self.active:
            return None
        return {
            "case_id": str(case_id),
            "status": "running",
            "payload": {"filenames": ["video1.mp4"]},
        }

    def cancel_case_active(self, case_id: str, *, reason: str = "") -> int:
        self.cancel_calls += 1
        was_active = self.active
        self.active = False
        return 1 if was_active else 0

    def clear_case(self, case_id: str) -> None:
        self.clear_calls += 1
        self.active = False


class _FakeProcessControlService:
    def __init__(self, app: FastAPI, queue_store: _TransitionQueueStore) -> None:
        self.app = app
        self.queue_store = queue_store
        self.calls = 0

    async def cancel_case_index_jobs(
        self,
        *,
        case_id: str,
        force: bool = False,
        reason: str = "",
    ) -> dict:
        self.calls += 1
        with self.app.state.index_jobs_lock:
            current = self.app.state.index_jobs.get(case_id)
            if isinstance(current, dict):
                current["cancel_requested"] = True
                current["status"] = "cancelled"
                current["running"] = False

        queue_cancelled = self.queue_store.cancel_case_active(case_id, reason=reason)
        return {
            "case_id": str(case_id),
            "cancel_requested": True,
            "task_cancelled": False,
            "queue_cancelled_count": int(queue_cancelled),
            "active_after_cancel": False,
        }


def _build_app(
    *,
    queue_store: object | None,
    process_control_service: object | None,
    delete_case_sync: object,
) -> FastAPI:
    app = FastAPI()
    app.state.index_jobs = {}
    app.state.index_tasks = {}
    app.state.index_jobs_lock = Lock()
    app.state.vector_stores = {}
    app.state.vector_stores_lock = Lock()
    app.state.temporal_stores = {}
    app.state.temporal_stores_lock = Lock()
    app.state.analysis_stores = {}
    app.state.analysis_stores_lock = Lock()
    app.state.index_queue_store = queue_store
    app.state.index_job_store = None
    app.state.video_pipeline_store = None
    app.state.process_control_service = process_control_service

    app.include_router(
        build_cases_router(
            create_case_sync=lambda _name: {"case_id": "unused", "name": "unused"},
            list_cases_sync=lambda: [],
            rename_case_sync=lambda _case_id, _name: {"case_id": "unused", "name": "unused"},
            delete_case_sync=delete_case_sync,
            normalize_case_id=lambda case_id: str(case_id).strip(),
            delete_quiescence_timeout_seconds=0.5,
            delete_poll_interval_seconds=0.05,
            delete_required_quiet_polls=1,
        )
    )
    return app


class CaseDeleteSafetyRouterTests(unittest.TestCase):
    def test_delete_case_returns_409_if_still_busy(self) -> None:
        queue_store = _BusyQueueStore()
        delete_calls = {"count": 0}

        def _delete_case_sync(case_id: str) -> dict:
            delete_calls["count"] += 1
            return {"case_id": case_id, "name": "Case A", "created_at": "2026-01-01T00:00:00+00:00"}

        app = _build_app(
            queue_store=queue_store,
            process_control_service=None,
            delete_case_sync=_delete_case_sync,
        )
        client = TestClient(app)
        response = client.delete("/cases/case_busy")

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertIn("still busy with background processing", payload["detail"])
        self.assertEqual(delete_calls["count"], 0)
        self.assertGreaterEqual(queue_store.cancel_calls, 1)

    def test_delete_case_succeeds_after_quiescence(self) -> None:
        queue_store = _TransitionQueueStore()
        delete_calls = {"count": 0}

        def _delete_case_sync(case_id: str) -> dict:
            delete_calls["count"] += 1
            return {
                "case_id": str(case_id),
                "name": "Case A",
                "created_at": "2026-01-01T00:00:00+00:00",
            }

        app = _build_app(
            queue_store=queue_store,
            process_control_service=None,
            delete_case_sync=_delete_case_sync,
        )
        app.state.index_jobs["case_a"] = {
            "status": "running",
            "running": True,
            "current_filename": "video1.mp4",
        }
        app.state.process_control_service = _FakeProcessControlService(app, queue_store)

        client = TestClient(app)
        response = client.delete("/cases/case_a")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["deleted_case_id"], "case_a")
        self.assertTrue(payload["cancel_requested"])
        self.assertGreaterEqual(int(payload["queue_cancelled_count"]), 1)
        self.assertEqual(delete_calls["count"], 1)
        self.assertGreaterEqual(queue_store.clear_calls, 1)
        self.assertNotIn("case_a", app.state.index_jobs)

if __name__ == "__main__":
    unittest.main()
