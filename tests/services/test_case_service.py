from __future__ import annotations

import unittest
from pathlib import Path

from backend.services.case_service import (
    build_case_paths,
    empty_cases_registry,
    find_case_locked,
    normalize_case_id,
)


class CaseServiceTests(unittest.TestCase):
    def test_normalize_case_id_sanitizes_and_trims(self) -> None:
        self.assertEqual(normalize_case_id("  case-001  "), "case-001")
        self.assertEqual(normalize_case_id("Case Name/Unsafe"), "Case_Name_Unsafe")

    def test_normalize_case_id_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            normalize_case_id("")
        with self.assertRaises(ValueError):
            normalize_case_id("   ")

    def test_build_case_paths_layout(self) -> None:
        paths = build_case_paths("case_abc", cases_dir=Path("cases_root"))
        self.assertEqual(paths.case_id, "case_abc")
        self.assertEqual(paths.case_dir, Path("cases_root") / "case_abc")
        self.assertEqual(paths.videos_dir, Path("cases_root") / "case_abc" / "videos")
        self.assertEqual(paths.thumbnails_dir, Path("cases_root") / "case_abc" / "thumbnails")
        self.assertEqual(paths.data_dir, Path("cases_root") / "case_abc" / "data")
        self.assertEqual(paths.index_path, Path("cases_root") / "case_abc" / "data" / "faiss.index")

    def test_empty_cases_registry_shape(self) -> None:
        payload = empty_cases_registry()
        self.assertEqual(payload["next_numeric_id"], 1)
        self.assertEqual(payload["cases"], [])

    def test_find_case_locked(self) -> None:
        payload = {
            "cases": [
                {"case_id": "a", "name": "Alpha"},
                {"case_id": "b", "name": "Beta"},
            ]
        }
        self.assertEqual(find_case_locked(payload, "b"), {"case_id": "b", "name": "Beta"})
        self.assertIsNone(find_case_locked(payload, "missing"))


if __name__ == "__main__":
    unittest.main()

