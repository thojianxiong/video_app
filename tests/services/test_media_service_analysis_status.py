from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from backend.services.media_service import MediaService
from backend.stores.index_queue_store import IndexQueueStore
from backend.stores.video_pipeline_store import VideoPipelineStore


class MediaServiceAnalysisStatusTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests") / ".tmp_media_service_analysis_status"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        self.default_case_id: str | None = "case_a"
        self.queue_store = IndexQueueStore(self.tmp_dir / "index_queue.db")
        self.pipeline_store = VideoPipelineStore(self.tmp_dir / "video_pipeline.db")

        state = SimpleNamespace(
            index_queue_store=self.queue_store,
            video_pipeline_store=self.pipeline_store,
            index_jobs={},
            index_jobs_lock=Lock(),
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
            delete_video_sync=lambda *_args, **_kwargs: {},
            process_video_sync=lambda *_args, **_kwargs: {},
            resolve_index_filenames=lambda *_args, **_kwargs: [],
            find_running_index_case_id_locked=lambda *_args, **_kwargs: "",
            new_index_job_record=lambda *_args, **_kwargs: {},
            run_index_job_async=lambda *_args, **_kwargs: None,
            index_job_snapshot=lambda job, *, case_id: {"case_id": case_id, "status": "idle", **(job or {})},
        )

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def _resolve_case_id_or_default(self, case_id: str | None) -> str:
        normalized = str(case_id or "").strip()
        if normalized:
            return normalized
        if self.default_case_id and str(self.default_case_id).strip():
            return str(self.default_case_id).strip()
        raise ValueError("No cases available. Create a case first.")

    @staticmethod
    def _get_case_paths_or_raise(case_id: str):
        normalized = str(case_id or "").strip()
        if not normalized or normalized == "missing":
            raise KeyError(case_id)
        return SimpleNamespace(case_id=normalized)

    def _enqueue_analysis_job(self, *, filenames: list[str], metadata: dict | None = None) -> dict:
        return self.queue_store.enqueue_or_get_active(
            case_id="case_a",
            filenames=filenames,
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="analysis",
            priority=70,
            metadata=metadata or {},
        )

    async def test_get_background_analysis_status_running(self) -> None:
        queued = self._enqueue_analysis_job(
            filenames=["a.mp4", "b.mp4", "c.mp4"],
            metadata={
                "analysis_face_people": True,
                "analysis_vehicles": False,
            },
        )
        claimed = self.queue_store.claim_next_queued()
        self.assertIsNotNone(claimed)
        self.assertEqual(int(claimed["job_id"]), int(queued["job_id"]))

        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="a.mp4",
            stage="analysis",
            status="completed",
            event="analysis_completed",
        )
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="b.mp4",
            stage="analysis",
            status="running",
            event="analysis_running",
        )

        payload = await self.service.get_background_analysis_status("case_a")
        self.assertEqual(payload["case_id"], "case_a")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(int(payload["queue"]["job_id"]), int(queued["job_id"]))
        self.assertEqual(str(payload["queue"]["status"]), "running")
        self.assertEqual(int(payload["progress"]["completed"]), 1)
        self.assertEqual(int(payload["progress"]["total"]), 3)
        self.assertAlmostEqual(float(payload["progress"]["percent"]), 33.3333, places=2)
        self.assertEqual(payload["filenames"], ["a.mp4", "b.mp4", "c.mp4"])
        self.assertTrue(bool(payload["analysis"]["face_people"]))
        self.assertFalse(bool(payload["analysis"]["vehicles"]))
        self.assertIn("running", str(payload["message"]).lower())

    async def test_get_background_analysis_status_completed_with_errors(self) -> None:
        queued = self._enqueue_analysis_job(
            filenames=["a.mp4", "b.mp4", "c.mp4"],
            metadata={
                "analysis_face_people": True,
                "analysis_vehicles": True,
            },
        )
        claimed = self.queue_store.claim_next_queued()
        self.assertIsNotNone(claimed)
        self.queue_store.complete_job(
            job_id=int(queued["job_id"]),
            status="completed",
            error="Completed with errors (1/3 failed).",
        )

        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="a.mp4",
            stage="analysis",
            status="completed",
            event="analysis_completed",
        )
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="b.mp4",
            stage="analysis",
            status="failed",
            event="analysis_failed",
            error="detector unavailable",
        )
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="c.mp4",
            stage="analysis",
            status="skipped",
            event="analysis_skipped",
        )

        payload = await self.service.get_background_analysis_status("case_a")
        self.assertEqual(payload["status"], "completed_with_errors")
        self.assertEqual(str(payload["queue"]["status"]), "completed")
        self.assertEqual(int(payload["queue"]["job_id"]), int(queued["job_id"]))
        self.assertTrue(bool(payload["queue"]["finished_at"]))
        self.assertEqual(int(payload["progress"]["completed"]), 3)
        self.assertEqual(int(payload["progress"]["total"]), 3)
        self.assertAlmostEqual(float(payload["progress"]["percent"]), 100.0, places=4)
        self.assertTrue(bool(payload["analysis"]["face_people"]))
        self.assertTrue(bool(payload["analysis"]["vehicles"]))
        self.assertIn("errors", str(payload["message"]).lower())

    async def test_get_background_analysis_status_failed_terminal_job(self) -> None:
        queued = self._enqueue_analysis_job(
            filenames=["z.mp4"],
            metadata={
                "analysis_face_people": False,
                "analysis_vehicles": True,
            },
        )
        claimed = self.queue_store.claim_next_queued()
        self.assertIsNotNone(claimed)
        self.queue_store.complete_job(
            job_id=int(queued["job_id"]),
            status="failed",
            error="analysis model unavailable",
        )

        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="z.mp4",
            stage="analysis",
            status="failed",
            event="analysis_failed",
            error="analysis model unavailable",
        )

        payload = await self.service.get_background_analysis_status("case_a")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(str(payload["queue"]["status"]), "failed")
        self.assertTrue(bool(payload["queue"]["finished_at"]))
        self.assertEqual(int(payload["progress"]["completed"]), 1)
        self.assertEqual(int(payload["progress"]["total"]), 1)
        self.assertAlmostEqual(float(payload["progress"]["percent"]), 100.0, places=4)
        self.assertFalse(bool(payload["analysis"]["face_people"]))
        self.assertTrue(bool(payload["analysis"]["vehicles"]))
        self.assertIn("model unavailable", str(payload["message"]).lower())

    async def test_get_background_analysis_status_filters_by_category(self) -> None:
        queued = self._enqueue_analysis_job(
            filenames=["fp1.mp4", "fp2.mp4", "v1.mp4", "v2.mp4"],
            metadata={
                "analysis_face_people": True,
                "analysis_vehicles": True,
                "analysis_face_people_filenames": ["fp1.mp4", "fp2.mp4"],
                "analysis_vehicles_filenames": ["v1.mp4", "v2.mp4"],
            },
        )
        claimed = self.queue_store.claim_next_queued()
        self.assertIsNotNone(claimed)
        self.assertEqual(int(claimed["job_id"]), int(queued["job_id"]))

        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="fp1.mp4",
            stage="analysis",
            status="completed",
            event="analysis_completed",
        )
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="fp2.mp4",
            stage="analysis",
            status="running",
            event="analysis_running",
        )
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="v1.mp4",
            stage="analysis",
            status="pending",
            event="analysis_pending",
        )
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="v2.mp4",
            stage="analysis",
            status="pending",
            event="analysis_pending",
        )

        face_payload = await self.service.get_background_analysis_status("case_a", "face_people")
        self.assertEqual(face_payload["filenames"], ["fp1.mp4", "fp2.mp4"])
        self.assertTrue(bool(face_payload["analysis"]["face_people"]))
        self.assertFalse(bool(face_payload["analysis"]["vehicles"]))
        self.assertEqual(int(face_payload["progress"]["completed"]), 1)
        self.assertEqual(int(face_payload["progress"]["total"]), 2)

        vehicle_payload = await self.service.get_background_analysis_status("case_a", "vehicles")
        self.assertEqual(vehicle_payload["filenames"], ["v1.mp4", "v2.mp4"])
        self.assertFalse(bool(vehicle_payload["analysis"]["face_people"]))
        self.assertTrue(bool(vehicle_payload["analysis"]["vehicles"]))
        self.assertEqual(int(vehicle_payload["progress"]["completed"]), 0)
        self.assertEqual(int(vehicle_payload["progress"]["total"]), 2)

    async def test_get_background_analysis_status_interrupted_surfaces_queued_not_started(self) -> None:
        queued = self._enqueue_analysis_job(
            filenames=["a.mp4", "b.mp4", "c.mp4"],
            metadata={
                "analysis_face_people": True,
                "analysis_vehicles": True,
            },
        )
        claimed = self.queue_store.claim_next_queued()
        self.assertIsNotNone(claimed)
        self.assertEqual(int(claimed["job_id"]), int(queued["job_id"]))

        # Simulate one processed file before startup interruption.
        self.pipeline_store.update_stage(
            case_id="case_a",
            filename="a.mp4",
            stage="analysis",
            status="completed",
            event="analysis_completed",
        )

        changed = self.queue_store.mark_running_jobs_interrupted()
        self.assertEqual(changed, 1)

        payload = await self.service.get_background_analysis_status("case_a")
        self.assertEqual(payload["status"], "interrupted")
        self.assertEqual(str(payload["queue"]["status"]), "interrupted")
        self.assertEqual(int(payload["queue"]["job_id"]), int(queued["job_id"]))
        self.assertEqual(payload["filenames"], ["a.mp4", "b.mp4", "c.mp4"])
        self.assertIn("b.mp4", payload["filenames"])
        self.assertIn("c.mp4", payload["filenames"])
        self.assertEqual(int(payload["progress"]["completed"]), 1)
        self.assertEqual(int(payload["progress"]["total"]), 3)
        self.assertAlmostEqual(float(payload["progress"]["percent"]), 33.3333, places=2)
        self.assertIn("interrupted", str(payload["message"]).lower())

    async def test_get_background_analysis_status_returns_idle_without_default_case(self) -> None:
        self.default_case_id = None
        payload = await self.service.get_background_analysis_status(None)
        self.assertEqual(payload["case_id"], "")
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(int(payload["queue"]["job_id"]), 0)
        self.assertEqual(int(payload["progress"]["total"]), 0)
        self.assertEqual(payload["filenames"], [])


if __name__ == "__main__":
    unittest.main()
