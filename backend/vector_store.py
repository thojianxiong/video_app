from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import faiss
import numpy as np


class VectorStore:
    def __init__(
        self,
        index_path: Path,
        metadata_path: Path,
        expected_dimension: int | None = None,
    ) -> None:
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.dimension: int | None = None
        self.next_vector_id = 0
        self.entries: dict[int, dict[str, Any]] = {}
        self.processed_videos: dict[str, dict[str, Any]] = {}
        self.video_analysis: dict[str, dict[str, Any]] = {}
        self.index: faiss.IndexIDMap2 | None = None
        self._lock = Lock()
        self._load(expected_dimension=expected_dimension)

    @staticmethod
    def build_video_key(signature: str, frame_interval_seconds: float) -> str:
        return f"{signature}|{frame_interval_seconds:.3f}"

    @staticmethod
    def build_analysis_key(signature: str, analysis_interval_seconds: float) -> str:
        return f"{signature}|{analysis_interval_seconds:.3f}"

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _create_index(self, dimension: int) -> faiss.IndexIDMap2:
        return faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))

    def _load(self, expected_dimension: int | None = None) -> None:
        if self.metadata_path.exists():
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self.dimension = payload.get("dimension")
            self.next_vector_id = int(payload.get("next_vector_id", 0))
            self.entries = {
                int(item["id"]): item for item in payload.get("entries", [])
            }
            self.processed_videos = payload.get("processed_videos", {})
            raw_video_analysis = payload.get("video_analysis", {})
            self.video_analysis = (
                raw_video_analysis if isinstance(raw_video_analysis, dict) else {}
            )

            if self.next_vector_id <= 0 and self.entries:
                self.next_vector_id = max(self.entries) + 1

        if self.index_path.exists():
            loaded_index = faiss.read_index(str(self.index_path))
            if not isinstance(loaded_index, faiss.IndexIDMap2):
                raise RuntimeError("Stored FAISS index must be an IndexIDMap2")
            self.index = loaded_index
            if self.dimension is None:
                self.dimension = int(self.index.d)

        if self.dimension is None and expected_dimension is not None:
            self.dimension = int(expected_dimension)
            self.index = self._create_index(self.dimension)

        if self.dimension is not None and self.index is None:
            self.index = self._create_index(self.dimension)

        if (
            expected_dimension is not None
            and self.dimension is not None
            and int(expected_dimension) != int(self.dimension)
        ):
            raise RuntimeError(
                f"Embedding dimension mismatch: store={self.dimension}, model={expected_dimension}"
            )

    def _save_locked(self) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if self.index is not None:
            faiss.write_index(self.index, str(self.index_path))

        metadata = {
            "dimension": self.dimension,
            "next_vector_id": self.next_vector_id,
            "entries": [self.entries[key] for key in sorted(self.entries)],
            "processed_videos": self.processed_videos,
            "video_analysis": self.video_analysis,
        }
        self.metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

    def _remove_ids_locked(self, vector_ids: list[int]) -> None:
        if not vector_ids or self.index is None:
            return

        ids_array = np.asarray(vector_ids, dtype=np.int64)
        self.index.remove_ids(ids_array)
        for vector_id in vector_ids:
            self.entries.pop(int(vector_id), None)

    def is_video_indexed(self, signature: str, frame_interval_seconds: float) -> bool:
        key = self.build_video_key(signature, frame_interval_seconds)
        return key in self.processed_videos

    def get_indexed_frame_count(
        self,
        signature: str,
        frame_interval_seconds: float,
    ) -> int:
        key = self.build_video_key(signature, frame_interval_seconds)
        item = self.processed_videos.get(key)
        if not item:
            return 0
        return len(item.get("vector_ids", []))

    def indexed_counts_by_filename(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.processed_videos.values():
            filename = item.get("video_filename")
            if not filename:
                continue
            counts[filename] = counts.get(filename, 0) + len(item.get("vector_ids", []))
        return counts

    def get_video_analysis(
        self,
        signature: str,
        analysis_interval_seconds: float,
    ) -> dict[str, Any]:
        key = self.build_analysis_key(signature, analysis_interval_seconds)
        item = self.video_analysis.get(key)
        if not isinstance(item, dict):
            return {}
        return dict(item)

    def get_video_analysis_status(
        self,
        signature: str,
        analysis_interval_seconds: float,
    ) -> dict[str, bool]:
        item = self.get_video_analysis(signature, analysis_interval_seconds)

        face_people = item.get("face_people", {})
        vehicles = item.get("vehicles", {})
        return {
            "face_people": bool(face_people.get("processed")),
            "vehicles": bool(vehicles.get("processed")),
        }

    def upsert_video_analysis(
        self,
        *,
        signature: str,
        analysis_interval_seconds: float,
        video_filename: str,
        selected: dict[str, bool],
        frame_count: int,
        face_count: int,
        people_count: int,
        vehicle_count: int,
        face_people_hit_frames: int,
        vehicle_hit_frames: int,
        face_people_first_hit_seconds: float | None,
        vehicle_first_hit_seconds: float | None,
        detector: str,
        force: bool = False,
    ) -> dict[str, Any]:
        key = self.build_analysis_key(signature, analysis_interval_seconds)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            existing = self.video_analysis.get(key, {})
            face_existing = (
                existing.get("face_people")
                if isinstance(existing.get("face_people"), dict)
                else {}
            )
            vehicle_existing = (
                existing.get("vehicles")
                if isinstance(existing.get("vehicles"), dict)
                else {}
            )

            selected_face = bool(selected.get("face_people"))
            selected_vehicle = bool(selected.get("vehicles"))

            face_payload = {
                "processed": bool(face_existing.get("processed")),
                "processed_at": face_existing.get("processed_at"),
                "face_count": int(face_existing.get("face_count", 0)),
                "people_count": int(face_existing.get("people_count", 0)),
                "hit_frames": int(face_existing.get("hit_frames", 0)),
                "first_hit_seconds": (
                    self._optional_float(face_existing.get("first_hit_seconds"))
                ),
            }
            if selected_face and (force or not face_payload["processed"]):
                face_payload = {
                    "processed": True,
                    "processed_at": now_iso,
                    "face_count": int(face_count),
                    "people_count": int(people_count),
                    "hit_frames": int(face_people_hit_frames),
                    "first_hit_seconds": (
                        float(face_people_first_hit_seconds)
                        if face_people_first_hit_seconds is not None
                        and float(face_people_first_hit_seconds) >= 0
                        else None
                    ),
                }

            vehicle_payload = {
                "processed": bool(vehicle_existing.get("processed")),
                "processed_at": vehicle_existing.get("processed_at"),
                "vehicle_count": int(vehicle_existing.get("vehicle_count", 0)),
                "hit_frames": int(vehicle_existing.get("hit_frames", 0)),
                "first_hit_seconds": (
                    self._optional_float(vehicle_existing.get("first_hit_seconds"))
                ),
            }
            if selected_vehicle and (force or not vehicle_payload["processed"]):
                vehicle_payload = {
                    "processed": True,
                    "processed_at": now_iso,
                    "vehicle_count": int(vehicle_count),
                    "hit_frames": int(vehicle_hit_frames),
                    "first_hit_seconds": (
                        float(vehicle_first_hit_seconds)
                        if vehicle_first_hit_seconds is not None
                        and float(vehicle_first_hit_seconds) >= 0
                        else None
                    ),
                }

            record = {
                "video_filename": video_filename,
                "signature": signature,
                "analysis_interval_seconds": float(analysis_interval_seconds),
                "processed_frames": int(frame_count),
                "detector": detector,
                "updated_at": now_iso,
                "face_people": face_payload,
                "vehicles": vehicle_payload,
            }
            self.video_analysis[key] = record
            self._save_locked()
            return dict(record)

    def analysis_summary_by_filename(self) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}

        for item in self.video_analysis.values():
            if not isinstance(item, dict):
                continue
            filename = str(item.get("video_filename") or "").strip()
            if not filename:
                continue

            face_info = item.get("face_people", {})
            vehicle_info = item.get("vehicles", {})
            processed_frames = int(item.get("processed_frames", 0))

            existing = summary.setdefault(
                filename,
                {
                    "processed_frames": 0,
                    "face_people": {
                        "processed": False,
                        "face_count": 0,
                        "people_count": 0,
                        "hit_frames": 0,
                        "first_hit_seconds": None,
                    },
                    "vehicles": {
                        "processed": False,
                        "vehicle_count": 0,
                        "hit_frames": 0,
                        "first_hit_seconds": None,
                    },
                },
            )
            existing["processed_frames"] = max(existing["processed_frames"], processed_frames)

            if isinstance(face_info, dict) and face_info.get("processed"):
                existing["face_people"]["processed"] = True
                existing["face_people"]["face_count"] = max(
                    int(existing["face_people"]["face_count"]),
                    int(face_info.get("face_count", 0)),
                )
                existing["face_people"]["people_count"] = max(
                    int(existing["face_people"]["people_count"]),
                    int(face_info.get("people_count", 0)),
                )
                existing["face_people"]["hit_frames"] = max(
                    int(existing["face_people"]["hit_frames"]),
                    int(face_info.get("hit_frames", 0)),
                )
                first_hit = face_info.get("first_hit_seconds")
                first_hit_float = self._optional_float(first_hit)
                if first_hit_float is not None:
                    existing_first = existing["face_people"].get("first_hit_seconds")
                    if existing_first is None:
                        existing["face_people"]["first_hit_seconds"] = first_hit_float
                    else:
                        existing["face_people"]["first_hit_seconds"] = min(
                            float(existing_first),
                            first_hit_float,
                        )

            if isinstance(vehicle_info, dict) and vehicle_info.get("processed"):
                existing["vehicles"]["processed"] = True
                existing["vehicles"]["vehicle_count"] = max(
                    int(existing["vehicles"]["vehicle_count"]),
                    int(vehicle_info.get("vehicle_count", 0)),
                )
                existing["vehicles"]["hit_frames"] = max(
                    int(existing["vehicles"]["hit_frames"]),
                    int(vehicle_info.get("hit_frames", 0)),
                )
                first_hit = vehicle_info.get("first_hit_seconds")
                first_hit_float = self._optional_float(first_hit)
                if first_hit_float is not None:
                    existing_first = existing["vehicles"].get("first_hit_seconds")
                    if existing_first is None:
                        existing["vehicles"]["first_hit_seconds"] = first_hit_float
                    else:
                        existing["vehicles"]["first_hit_seconds"] = min(
                            float(existing_first),
                            first_hit_float,
                        )

        return summary

    def upsert_video_embeddings(
        self,
        *,
        signature: str,
        frame_interval_seconds: float,
        video_filename: str,
        records: list[dict[str, Any]],
        embeddings: np.ndarray,
        force: bool = False,
    ) -> dict[str, Any]:
        key = self.build_video_key(signature, frame_interval_seconds)

        with self._lock:
            existing = self.processed_videos.get(key)
            if existing and not force:
                return {
                    "status": "skipped",
                    "indexed_frames": len(existing.get("vector_ids", [])),
                }

            if existing and force:
                self._remove_ids_locked(existing.get("vector_ids", []))
                self.processed_videos.pop(key, None)

            embeddings = np.asarray(embeddings, dtype=np.float32)
            if embeddings.size == 0 or not records:
                self.processed_videos[key] = {
                    "video_filename": video_filename,
                    "signature": signature,
                    "frame_interval_seconds": frame_interval_seconds,
                    "vector_ids": [],
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                self._save_locked()
                return {"status": "processed", "indexed_frames": 0}

            if embeddings.ndim != 2:
                raise ValueError("Embeddings must be a 2D array")

            if embeddings.shape[0] != len(records):
                raise ValueError("Embedding count must match metadata record count")

            if self.dimension is None:
                self.dimension = int(embeddings.shape[1])

            if embeddings.shape[1] != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected={self.dimension}, got={embeddings.shape[1]}"
                )

            if self.index is None:
                self.index = self._create_index(self.dimension)

            vector_ids = np.arange(
                self.next_vector_id,
                self.next_vector_id + embeddings.shape[0],
                dtype=np.int64,
            )
            self.next_vector_id += embeddings.shape[0]

            contiguous_embeddings = np.ascontiguousarray(embeddings.astype(np.float32))
            self.index.add_with_ids(contiguous_embeddings, vector_ids)

            created_ids = vector_ids.tolist()
            for vector_id, record in zip(created_ids, records):
                self.entries[vector_id] = {
                    "id": vector_id,
                    "video_filename": video_filename,
                    "timestamp_seconds": float(record["timestamp_seconds"]),
                    "thumbnail_path": record["thumbnail_path"],
                }

            self.processed_videos[key] = {
                "video_filename": video_filename,
                "signature": signature,
                "frame_interval_seconds": frame_interval_seconds,
                "vector_ids": created_ids,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_locked()

            return {"status": "processed", "indexed_frames": len(created_ids)}

    def delete_video_embeddings(self, video_filename: str) -> dict[str, int]:
        target_filename = str(video_filename or "").strip()
        if not target_filename:
            return {"removed_vectors": 0, "removed_records": 0, "removed_analysis_records": 0}

        with self._lock:
            matching_keys = [
                key
                for key, value in self.processed_videos.items()
                if str(value.get("video_filename", "")) == target_filename
            ]
            analysis_keys = [
                key
                for key, value in self.video_analysis.items()
                if str(value.get("video_filename", "")) == target_filename
            ]
            if not matching_keys and not analysis_keys:
                return {"removed_vectors": 0, "removed_records": 0, "removed_analysis_records": 0}

            vector_ids: list[int] = []
            for key in matching_keys:
                item = self.processed_videos.get(key, {})
                vector_ids.extend(item.get("vector_ids", []))

            removed_vectors = len(vector_ids)
            removed_records = len(matching_keys)
            removed_analysis_records = len(analysis_keys)
            self._remove_ids_locked(vector_ids)
            for key in matching_keys:
                self.processed_videos.pop(key, None)
            for key in analysis_keys:
                self.video_analysis.pop(key, None)

            self._save_locked()
            return {
                "removed_vectors": removed_vectors,
                "removed_records": removed_records,
                "removed_analysis_records": removed_analysis_records,
            }

    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> list[dict[str, Any]]:
        if top_k <= 0:
            return []

        with self._lock:
            if self.index is None or self.index.ntotal == 0:
                return []

            query = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
            if self.dimension is not None and query.shape[1] != self.dimension:
                raise ValueError(
                    f"Query dimension mismatch: expected={self.dimension}, got={query.shape[1]}"
                )

            faiss.normalize_L2(query)
            search_k = min(int(top_k), int(self.index.ntotal))
            scores, ids = self.index.search(query, search_k)

            results: list[dict[str, Any]] = []
            for score, vector_id in zip(scores[0], ids[0]):
                if vector_id == -1:
                    continue

                item = self.entries.get(int(vector_id))
                if not item:
                    continue

                results.append(
                    {
                        "video_filename": item["video_filename"],
                        "timestamp_seconds": item["timestamp_seconds"],
                        "thumbnail_path": item["thumbnail_path"],
                        "similarity_score": float(score),
                    }
                )

            return results
