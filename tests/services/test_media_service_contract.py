from __future__ import annotations

import unittest
from pathlib import Path

from backend.services.media_service import MediaService


class MediaContractTests(unittest.TestCase):
    def test_canonical_status_ready_when_indexed(self) -> None:
        pipeline = MediaService._default_pipeline("case_a", "video_a.mp4")
        contract = MediaService._build_video_media_contract(
            case_id="case_a",
            file_path=Path("video_a.mp4"),
            video_url="/media/cases/case_a/videos/video_a.mp4",
            preview_thumbnail_url="/media/cases/case_a/thumbnails/video_a.jpg",
            size_bytes=1234,
            indexed_frames=10,
            indexed_windows=3,
            analysis=MediaService._default_analysis_summary(),
            pipeline=pipeline,
        )
        self.assertEqual(contract["status"]["overall"], "ready")
        self.assertEqual(contract["status"]["indexing"], "indexed")
        self.assertTrue(contract["lifecycle"]["semantic_index_ready"])
        self.assertTrue(contract["lifecycle"]["search_ready"])

    def test_canonical_status_processing_when_pipeline_running(self) -> None:
        pipeline = MediaService._default_pipeline("case_b", "video_b.mp4")
        pipeline["overall_status"] = "running"
        pipeline["current_stage"] = "normalize"
        pipeline["stages"]["normalize"] = {
            "status": "running",
            "error": "",
            "finished_at": "",
        }
        contract = MediaService._build_video_media_contract(
            case_id="case_b",
            file_path=Path("video_b.mp4"),
            video_url="/media/cases/case_b/videos/video_b.mp4",
            preview_thumbnail_url="",
            size_bytes=999,
            indexed_frames=0,
            indexed_windows=0,
            analysis=MediaService._default_analysis_summary(),
            pipeline=pipeline,
        )
        self.assertEqual(contract["status"]["overall"], "processing")
        self.assertEqual(contract["status"]["indexing"], "not_indexed")
        self.assertTrue(contract["status"]["is_running"])

    def test_pipeline_errors_are_collected(self) -> None:
        pipeline = MediaService._default_pipeline("case_c", "video_c.mp4")
        pipeline["stages"]["ingest"] = {"status": "completed", "error": ""}
        pipeline["stages"]["normalize"] = {
            "status": "failed",
            "error": "ffmpeg failed",
            "finished_at": "",
        }
        pipeline["stages"]["analysis"] = {
            "status": "failed",
            "error": "detector unavailable",
            "finished_at": "",
        }
        errors = MediaService._pipeline_errors(pipeline)
        self.assertEqual(
            errors,
            [
                "normalize: ffmpeg failed",
                "analysis: detector unavailable",
            ],
        )


if __name__ == "__main__":
    unittest.main()

