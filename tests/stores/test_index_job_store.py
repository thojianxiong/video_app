from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from backend.stores.index_job_store import IndexJobStore


class IndexJobStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests") / ".tmp_index_job_store"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.tmp_dir / "index_jobs.db"
        self.store = IndexJobStore(self.db_path)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def test_upsert_and_get_case_snapshot(self) -> None:
        snapshot = {
            "case_id": "case_a",
            "status": "running",
            "running": True,
            "total": 10,
            "completed": 2,
            "updated_at": "2026-05-07T00:00:00+00:00",
        }
        self.store.upsert_snapshot(snapshot)

        loaded = self.store.get_case_snapshot("case_a")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["case_id"], "case_a")
        self.assertEqual(loaded["status"], "running")
        self.assertTrue(loaded["running"])
        self.assertEqual(loaded["completed"], 2)

    def test_load_all_snapshots(self) -> None:
        self.store.upsert_snapshot({"case_id": "case_1", "status": "completed", "running": False})
        self.store.upsert_snapshot({"case_id": "case_2", "status": "queued", "running": True})

        loaded = self.store.load_all_snapshots()
        self.assertEqual(set(loaded.keys()), {"case_1", "case_2"})
        self.assertEqual(loaded["case_1"]["status"], "completed")
        self.assertEqual(loaded["case_2"]["status"], "queued")

    def test_delete_case(self) -> None:
        self.store.upsert_snapshot({"case_id": "case_delete", "status": "completed", "running": False})
        self.assertIsNotNone(self.store.get_case_snapshot("case_delete"))

        self.store.delete_case("case_delete")
        self.assertIsNone(self.store.get_case_snapshot("case_delete"))

    def test_mark_incomplete_jobs_interrupted(self) -> None:
        self.store.upsert_snapshot(
            {
                "case_id": "case_running",
                "status": "running",
                "running": True,
                "errors": [],
            }
        )
        self.store.upsert_snapshot(
            {
                "case_id": "case_completed",
                "status": "completed",
                "running": False,
                "errors": [],
            }
        )
        self.store.upsert_snapshot(
            {
                "case_id": "case_queued",
                "status": "queued",
                "running": False,
                "errors": [],
            }
        )

        changed = self.store.mark_incomplete_jobs_interrupted()
        self.assertEqual(changed, 2)

        running = self.store.get_case_snapshot("case_running")
        queued = self.store.get_case_snapshot("case_queued")
        completed = self.store.get_case_snapshot("case_completed")

        self.assertEqual(running["status"], "interrupted")
        self.assertFalse(running["running"])
        self.assertTrue(running["cancel_requested"])
        self.assertIn("Marked interrupted on startup.", running["errors"])

        self.assertEqual(queued["status"], "interrupted")
        self.assertFalse(queued["running"])
        self.assertEqual(completed["status"], "completed")


if __name__ == "__main__":
    unittest.main()

