from __future__ import annotations

import sqlite3
import shutil
import time
import unittest
from pathlib import Path
from uuid import uuid4

from backend.stores.index_queue_store import IndexQueueStore


class IndexQueueStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests") / f".tmp_index_queue_store_{uuid4().hex}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.tmp_dir / "index_queue.db"
        self.store = IndexQueueStore(self.db_path)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            last_error = None
            for _ in range(6):
                try:
                    shutil.rmtree(self.tmp_dir)
                    last_error = None
                    break
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(0.1)
            if last_error is not None:
                # Best-effort cleanup on Windows; locked temp files can outlive test scope briefly.
                return

    def test_enqueue_claim_complete(self) -> None:
        queued = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        self.assertTrue(queued["created"])
        self.assertEqual(queued["status"], "queued")

        claimed = self.store.claim_next_queued()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["job_id"], queued["job_id"])
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["attempt_count"], 1)

        completed = self.store.complete_job(
            job_id=claimed["job_id"],
            status="completed",
            error="",
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.store.claim_next_queued(), None)

    def test_dedupe_same_payload(self) -> None:
        first = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4", "b.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        second = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["b.mp4", "a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(second["reason"], "duplicate_active_job")
        self.assertEqual(first["job_id"], second["job_id"])

    def test_case_active_appends_new_filenames(self) -> None:
        first = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        second = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["c.mp4"],
            frame_interval_seconds=1.0,
            batch_size=64,
            force=True,
        )
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(second["reason"], "appended_case_active_job")
        self.assertEqual(second["appended_count"], 1)
        payload = second.get("payload") if isinstance(second.get("payload"), dict) else {}
        filenames = [str(item) for item in (payload.get("filenames") or [])]
        self.assertEqual(filenames, ["a.mp4", "c.mp4"])

    def test_mark_running_interrupted(self) -> None:
        queued = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        claimed = self.store.claim_next_queued()
        self.assertEqual(claimed["status"], "running")
        changed = self.store.mark_running_jobs_interrupted()
        self.assertEqual(changed, 1)

        active = self.store.get_case_active("case_a")
        self.assertIsNone(active)
        # complete_job still works on interrupted rows if needed for cleanup semantics
        done = self.store.complete_job(
            job_id=queued["job_id"],
            status="interrupted",
            error="test",
        )
        self.assertEqual(done["status"], "interrupted")

    def test_clear_case(self) -> None:
        self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        self.store.enqueue_or_get_active(
            case_id="case_b",
            filenames=["b.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        self.store.clear_case("case_a")
        self.assertIsNone(self.store.get_case_active("case_a"))
        self.assertIsNotNone(self.store.get_case_active("case_b"))

    def test_cancel_case_active(self) -> None:
        queued = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
        )
        self.assertEqual(queued["status"], "queued")
        changed = self.store.cancel_case_active("case_a", reason="test cancel")
        self.assertEqual(changed, 1)
        self.assertIsNone(self.store.get_case_active("case_a"))

    def test_claim_respects_priority_then_fifo(self) -> None:
        low_priority = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            priority=60,
        )
        high_priority = self.store.enqueue_or_get_active(
            case_id="case_b",
            filenames=["b.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            priority=10,
        )
        medium_priority = self.store.enqueue_or_get_active(
            case_id="case_c",
            filenames=["c.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            priority=30,
        )

        claimed_first = self.store.claim_next_queued()
        claimed_second = self.store.claim_next_queued()
        claimed_third = self.store.claim_next_queued()

        self.assertEqual(claimed_first["job_id"], high_priority["job_id"])
        self.assertEqual(claimed_second["job_id"], medium_priority["job_id"])
        self.assertEqual(claimed_third["job_id"], low_priority["job_id"])

    def test_case_active_isolated_by_job_kind(self) -> None:
        semantic = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="semantic_index",
            priority=50,
        )
        triage = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="triage_timeline",
            priority=15,
        )
        self.assertNotEqual(semantic["job_id"], triage["job_id"])

        active_any = self.store.get_case_active("case_a")
        active_semantic = self.store.get_case_active("case_a", job_kind="semantic_index")
        active_triage = self.store.get_case_active("case_a", job_kind="triage_timeline")

        self.assertEqual(active_any["job_id"], triage["job_id"])
        self.assertEqual(active_semantic["job_id"], semantic["job_id"])
        self.assertEqual(active_triage["job_id"], triage["job_id"])

    def test_analysis_metadata_merges_when_appending_same_case_kind(self) -> None:
        first = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="analysis",
            priority=70,
            metadata={
                "analysis_face_people": True,
                "analysis_vehicles": False,
                "analysis_face_people_filenames": ["a.mp4"],
            },
        )
        second = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["b.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="analysis",
            priority=70,
            metadata={
                "analysis_face_people": False,
                "analysis_vehicles": True,
                "analysis_vehicles_filenames": ["b.mp4"],
            },
        )
        self.assertFalse(second["created"])
        self.assertEqual(second["reason"], "appended_case_active_job")
        payload = second.get("payload") if isinstance(second.get("payload"), dict) else {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        self.assertTrue(bool(metadata.get("analysis_face_people")))
        self.assertTrue(bool(metadata.get("analysis_vehicles")))
        self.assertEqual(
            metadata.get("analysis_face_people_filenames"),
            ["a.mp4"],
        )
        self.assertEqual(
            metadata.get("analysis_vehicles_filenames"),
            ["b.mp4"],
        )
        self.assertEqual(first["job_id"], second["job_id"])

    def test_get_case_latest_returns_terminal_job(self) -> None:
        first = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["a.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="analysis",
            priority=70,
        )
        first_running = self.store.claim_next_queued()
        self.assertIsNotNone(first_running)
        self.store.complete_job(
            job_id=int(first["job_id"]),
            status="completed",
            error="",
        )
        self.assertIsNone(self.store.get_case_active("case_a", job_kind="analysis"))

        second = self.store.enqueue_or_get_active(
            case_id="case_a",
            filenames=["b.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="analysis",
            priority=70,
        )
        second_running = self.store.claim_next_queued()
        self.assertIsNotNone(second_running)
        self.store.complete_job(
            job_id=int(second["job_id"]),
            status="failed",
            error="analysis failed",
        )
        self.assertIsNone(self.store.get_case_active("case_a", job_kind="analysis"))

        latest = self.store.get_case_latest("case_a", job_kind="analysis")
        self.assertIsNotNone(latest)
        self.assertEqual(int(latest["job_id"]), int(second["job_id"]))
        self.assertEqual(str(latest["status"]), "failed")
        self.assertEqual(int(latest.get("queue_position", -1)), 0)

    def test_upgrades_legacy_schema_missing_priority_and_job_kind(self) -> None:
        legacy_db_path = self.tmp_dir / "legacy_index_queue.db"
        with sqlite3.connect(str(legacy_db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE index_job_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    enqueued_at TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

        upgraded_store = IndexQueueStore(legacy_db_path)
        queued = upgraded_store.enqueue_or_get_active(
            case_id="legacy_case",
            filenames=["legacy.mp4"],
            frame_interval_seconds=1.0,
            batch_size=32,
            force=False,
            job_kind="analysis",
            priority=15,
        )

        self.assertEqual(str(queued["job_kind"]), "analysis")
        self.assertEqual(int(queued["priority"]), 15)
        self.assertTrue(bool(queued["created"]))


if __name__ == "__main__":
    unittest.main()
