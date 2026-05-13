from __future__ import annotations

import shutil
import time
import unittest
from pathlib import Path
from uuid import uuid4

from backend.stores.triage_timeline_store import TriageTimelineStore


class TriageTimelineStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests") / f".tmp_triage_timeline_store_{uuid4().hex}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.tmp_dir / "triage_timeline.db"
        self.store = TriageTimelineStore(self.db_path)

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

    def test_exact_and_stale_lookup(self) -> None:
        payload = {
            "video_filename": "a.mp4",
            "bucket_seconds": 1.0,
            "activity_timeline": {"values": [0.1, 0.3]},
            "audio_timeline": {"values": [0.2, 0.4]},
        }
        self.store.upsert_payload(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v1",
            payload=payload,
        )

        exact_hit = self.store.load_payload_exact(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v1",
        )
        self.assertEqual(exact_hit, payload)

        exact_miss = self.store.load_payload_exact(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v2",
        )
        self.assertIsNone(exact_miss)

        stale_hit = self.store.load_payload_stale_for_video(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
        )
        self.assertEqual(stale_hit, payload)

        stale_miss = self.store.load_payload_stale_for_video(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v2",
        )
        self.assertIsNone(stale_miss)

    def test_upsert_replaces_signature_for_same_bucket(self) -> None:
        self.store.upsert_payload(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v1",
            payload={"value": "v1"},
        )
        self.store.upsert_payload(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v2",
            payload={"value": "v2"},
        )

        old_exact = self.store.load_payload_exact(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v1",
        )
        self.assertIsNone(old_exact)

        new_exact = self.store.load_payload_exact(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v2",
        )
        self.assertEqual(new_exact, {"value": "v2"})

        stale = self.store.load_payload_stale_for_video(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
        )
        self.assertEqual(stale, {"value": "v2"})

    def test_delete_video_and_case(self) -> None:
        self.store.upsert_payload(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
            analysis_signature="analysis_sig_v1",
            payload={"value": "a"},
        )
        self.store.upsert_payload(
            case_id="case_a",
            filename="b.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v2",
            analysis_signature="analysis_sig_v2",
            payload={"value": "b"},
        )
        self.store.upsert_payload(
            case_id="case_b",
            filename="c.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v3",
            analysis_signature="analysis_sig_v3",
            payload={"value": "c"},
        )

        self.store.delete_video(case_id="case_a", filename="a.mp4")
        deleted_video = self.store.load_payload_stale_for_video(
            case_id="case_a",
            filename="a.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v1",
        )
        self.assertIsNone(deleted_video)

        remaining_video = self.store.load_payload_stale_for_video(
            case_id="case_a",
            filename="b.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v2",
        )
        self.assertEqual(remaining_video, {"value": "b"})

        self.store.delete_case("case_a")
        case_a_after_delete = self.store.load_payload_stale_for_video(
            case_id="case_a",
            filename="b.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v2",
        )
        self.assertIsNone(case_a_after_delete)

        case_b_still_exists = self.store.load_payload_stale_for_video(
            case_id="case_b",
            filename="c.mp4",
            bucket_seconds=1.0,
            video_signature="video_sig_v3",
        )
        self.assertEqual(case_b_still_exists, {"value": "c"})


if __name__ == "__main__":
    unittest.main()
