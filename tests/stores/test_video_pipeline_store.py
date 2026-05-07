from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from backend.stores.video_pipeline_store import VideoPipelineStore


class VideoPipelineStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests") / ".tmp_video_pipeline_store"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.tmp_dir / "video_pipeline.db"
        self.store = VideoPipelineStore(self.db_path)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def test_update_stage_lifecycle(self) -> None:
        self.store.ensure_snapshot("case_a", "video_a.mp4")
        self.store.update_stage(
            case_id="case_a",
            filename="video_a.mp4",
            stage="ingest",
            status="running",
            increment_attempt=True,
            event="ingest_started",
        )
        snapshot = self.store.update_stage(
            case_id="case_a",
            filename="video_a.mp4",
            stage="ingest",
            status="completed",
            event="ingest_completed",
            details={"bytes": 1024},
        )

        self.assertEqual(snapshot["overall_status"], "partial")
        ingest = snapshot["stages"]["ingest"]
        self.assertEqual(ingest["status"], "completed")
        self.assertEqual(ingest["attempts"], 1)
        self.assertEqual(ingest["details"]["bytes"], 1024)

    def test_set_metadata_and_list(self) -> None:
        self.store.ensure_snapshot("case_a", "video_a.mp4")
        self.store.set_metadata(
            "case_a",
            "video_a.mp4",
            {"source_filename": "raw.avi", "converted_to_mp4": True},
        )
        snapshots = self.store.list_case_snapshots("case_a")
        self.assertEqual(len(snapshots), 1)
        metadata = snapshots[0]["metadata"]
        self.assertEqual(metadata["source_filename"], "raw.avi")
        self.assertTrue(metadata["converted_to_mp4"])

    def test_mark_running_as_interrupted(self) -> None:
        self.store.update_stage(
            case_id="case_a",
            filename="video_a.mp4",
            stage="base_index",
            status="running",
            increment_attempt=True,
            event="index_started",
        )
        changed = self.store.mark_running_as_interrupted()
        self.assertEqual(changed, 1)

        snapshot = self.store.get_video_snapshot("case_a", "video_a.mp4")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["overall_status"], "interrupted")
        self.assertEqual(snapshot["stages"]["base_index"]["status"], "interrupted")

    def test_delete_video_and_case(self) -> None:
        self.store.ensure_snapshot("case_a", "video_1.mp4")
        self.store.ensure_snapshot("case_a", "video_2.mp4")
        self.store.ensure_snapshot("case_b", "video_3.mp4")

        self.store.delete_video("case_a", "video_1.mp4")
        self.assertIsNone(self.store.get_video_snapshot("case_a", "video_1.mp4"))
        self.assertIsNotNone(self.store.get_video_snapshot("case_a", "video_2.mp4"))

        self.store.delete_case("case_a")
        self.assertEqual(self.store.list_case_snapshots("case_a"), [])
        self.assertEqual(len(self.store.list_case_snapshots("case_b")), 1)


if __name__ == "__main__":
    unittest.main()

