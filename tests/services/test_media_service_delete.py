from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from fastapi import HTTPException

from backend.services.media_service import MediaService
from backend.stores.index_queue_store import IndexQueueStore
from backend.stores.video_pipeline_store import VideoPipelineStore


class MediaServiceDeleteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests") / ".tmp_media_service_delete"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        self.queue_store = IndexQueueStore(self.tmp_dir / "index_queue.db")
        self.pipeline_store = VideoPipelineStore(self.tmp_dir / "video_pipeline.db")
        self.delete_calls = 0

        state = SimpleNamespace(
            index_queue_store=self.queue_store,
            video_pipeline_store=self.pipeline_store,
            index_jobs={},
            index_jobs_lock=Lock(),
            index_tasks={},
            deleting_case_ids=set(),
            deleting_case_ids_lock=Lock(),
        )
        self.app = SimpleNamespace(state=state)
        self.service = MediaService(
            app=self.app,
            video_extensions={".mp4"},
            convert_to_mp4=lambda *_args, **_kwargs: None,
            generate_preview_thumbnail=lambda *_args, **_kwargs: None,
            resolve_case_id_or_default=self._resolve_case_id_or_default,
            get_case_paths_or_raise=self._get_case_paths_or_raise,
            is_supported_video=lambda *_args, **_kwargs: True,
            unique_video_path=lambda *_args, **_kwargs: ("video.mp4", Path("video.mp4")),
            write_upload_file=lambda *_args, **_kwargs: 0,
            truncate_error=lambda value, limit=180: str(value)[: int(limit)],
            preview_thumbnail_path=lambda *_args, **_kwargs: Path("thumb.jpg"),
            media_url_for_case_path=lambda _path: "",
            get_vector_store_for_case=lambda *_args, **_kwargs: (None, None),
            get_temporal_store_for_case=lambda *_args, **_kwargs: (None, None),
            delete_video_sync=self._delete_video_sync_ok,
            process_video_sync=lambda *_args, **_kwargs: {},
            resolve_index_filenames=lambda *_args, **_kwargs: [],
            find_running_index_case_id_locked=lambda *_args, **_kwargs: "",
            new_index_job_record=lambda *_args, **_kwargs: {},
            run_index_job_async=lambda *_args, **_kwargs: None,
            index_job_snapshot=lambda job, *, case_id: {"case_id": case_id, "status": "idle", **(job or {})},
        )
        self.service.DELETE_LOCK_CHECK_DELAY_SECONDS = 0.001
        self.service.DELETE_LOCK_CHECK_MAX_DELAY_SECONDS = 0.01
        self.service.DELETE_LOCK_CHECK_ATTEMPTS = 3
        self.service.DELETE_PERMISSION_RETRY_ATTEMPTS = 2

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    @staticmethod
    def _resolve_case_id_or_default(case_id: str | None) -> str:
        normalized = str(case_id or "").strip()
        if not normalized:
            raise ValueError("No cases available. Create a case first.")
        return normalized

    @staticmethod
    def _get_case_paths_or_raise(case_id: str):
        normalized = str(case_id or "").strip()
        if not normalized or normalized == "missing":
            raise KeyError(case_id)
        return SimpleNamespace(case_id=normalized)

    def _delete_video_sync_ok(self, case_id: str, filename: str) -> dict:
        self.delete_calls += 1
        return {
            "case_id": str(case_id),
            "filename": str(filename),
            "deleted": True,
        }

    def _enqueue_job(self, *, kind: str, filenames: list[str]) -> dict:
        priority = 70 if str(kind).strip().lower() == "analysis" else 50
        return self.queue_store.enqueue_or_get_active(
            case_id="case_a",
            filenames=filenames,
            frame_interval_seconds=1.0,
            batch_size=16,
            force=False,
            job_kind=kind,
            priority=priority,
        )

    async def test_delete_video_cancels_semantic_queue_target_then_deletes(self) -> None:
        self._enqueue_job(kind="semantic_index", filenames=["target.mp4", "other.mp4"])

        payload = await self.service.delete_video("case_a", "target.mp4")

        self.assertTrue(bool(payload.get("deleted")))
        self.assertEqual(self.delete_calls, 1)
        self.assertIsNone(
            self.queue_store.get_case_active("case_a", job_kind="semantic_index")
        )

    async def test_delete_video_blocks_when_semantic_active_on_other_file(self) -> None:
        self.app.state.index_jobs["case_a"] = {
            "status": "running",
            "running": True,
            "current_filename": "other.mp4",
            "filenames": ["other.mp4"],
        }
        self.service.DELETE_LOCK_CHECK_ATTEMPTS = 1

        with self.assertRaises(HTTPException) as raised:
            await self.service.delete_video("case_a", "target.mp4")

        self.assertEqual(int(raised.exception.status_code), 409)
        detail = str(raised.exception.detail).lower()
        self.assertIn("semantic indexing", detail)
        self.assertIn("other.mp4", detail)
        self.assertEqual(self.delete_calls, 0)

    async def test_delete_video_blocks_when_pipeline_stage_running(self) -> None:
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="target.mp4",
            stage="analysis",
            status="running",
            event="analysis_running",
        )
        self.service.DELETE_LOCK_CHECK_ATTEMPTS = 1

        with self.assertRaises(HTTPException) as raised:
            await self.service.delete_video("case_a", "target.mp4")

        self.assertEqual(int(raised.exception.status_code), 409)
        detail = str(raised.exception.detail).lower()
        self.assertIn("pipeline stage 'analysis'", detail)
        self.assertEqual(self.delete_calls, 0)

    async def test_delete_video_cancels_analysis_queue_target_without_process_control(self) -> None:
        self._enqueue_job(kind="analysis", filenames=["target.mp4"])
        payload = await self.service.delete_video("case_a", "target.mp4")
        self.assertTrue(bool(payload.get("deleted")))
        self.assertEqual(self.delete_calls, 1)
        self.assertIsNone(self.queue_store.get_case_active("case_a", job_kind="analysis"))

    async def test_delete_video_permission_error_retries_and_returns_context(self) -> None:
        attempts = {"count": 0}

        def _delete_always_locked(_case_id: str, _filename: str) -> dict:
            attempts["count"] += 1
            raise PermissionError("locked by player")

        self.service.delete_video_sync = _delete_always_locked

        with self.assertRaises(HTTPException) as raised:
            await self.service.delete_video("case_a", "target.mp4")

        self.assertEqual(int(raised.exception.status_code), 409)
        detail = str(raised.exception.detail)
        self.assertIn("Failed to delete 'target.mp4' in case 'case_a'.", detail)
        self.assertIn("locked by player", detail)
        self.assertEqual(attempts["count"], int(self.service.DELETE_PERMISSION_RETRY_ATTEMPTS))

    async def test_delete_video_returns_409_when_same_target_delete_is_in_progress(self) -> None:
        self.app.state.deleting_video_keys = {"case_a::target.mp4"}
        self.app.state.deleting_video_keys_lock = Lock()

        with self.assertRaises(HTTPException) as raised:
            await self.service.delete_video("case_a", "target.mp4")

        self.assertEqual(int(raised.exception.status_code), 409)
        self.assertIn("Delete already in progress", str(raised.exception.detail))


if __name__ == "__main__":
    unittest.main()
