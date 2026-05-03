from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import faiss
import numpy as np


class TemporalWindowStore:
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
        self.index: faiss.IndexIDMap2 | None = None
        self._lock = Lock()
        self._load(expected_dimension=expected_dimension)

    @staticmethod
    def build_video_key(
        signature: str,
        frame_interval_seconds: float,
        window_seconds: float,
        stride_seconds: float,
    ) -> str:
        return (
            f"{signature}|{frame_interval_seconds:.3f}|"
            f"{window_seconds:.3f}|{stride_seconds:.3f}"
        )

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
            raw_processed = payload.get("processed_videos", {})
            self.processed_videos = (
                raw_processed if isinstance(raw_processed, dict) else {}
            )

            if self.next_vector_id <= 0 and self.entries:
                self.next_vector_id = max(self.entries) + 1

        if self.index_path.exists():
            loaded_index = faiss.read_index(str(self.index_path))
            if not isinstance(loaded_index, faiss.IndexIDMap2):
                raise RuntimeError("Stored temporal FAISS index must be an IndexIDMap2")
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
                "Temporal embedding dimension mismatch: "
                f"store={self.dimension}, model={expected_dimension}"
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

    def is_video_indexed(
        self,
        signature: str,
        frame_interval_seconds: float,
        window_seconds: float,
        stride_seconds: float,
    ) -> bool:
        key = self.build_video_key(
            signature,
            frame_interval_seconds,
            window_seconds,
            stride_seconds,
        )
        return key in self.processed_videos

    def get_indexed_window_count(
        self,
        signature: str,
        frame_interval_seconds: float,
        window_seconds: float,
        stride_seconds: float,
    ) -> int:
        key = self.build_video_key(
            signature,
            frame_interval_seconds,
            window_seconds,
            stride_seconds,
        )
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

    def upsert_video_windows(
        self,
        *,
        signature: str,
        frame_interval_seconds: float,
        window_seconds: float,
        stride_seconds: float,
        video_filename: str,
        records: list[dict[str, Any]],
        embeddings: np.ndarray,
        force: bool = False,
    ) -> dict[str, Any]:
        key = self.build_video_key(
            signature,
            frame_interval_seconds,
            window_seconds,
            stride_seconds,
        )

        with self._lock:
            existing = self.processed_videos.get(key)
            if existing and not force:
                return {
                    "status": "skipped",
                    "indexed_windows": len(existing.get("vector_ids", [])),
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
                    "window_seconds": window_seconds,
                    "stride_seconds": stride_seconds,
                    "vector_ids": [],
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                self._save_locked()
                return {"status": "processed", "indexed_windows": 0}

            if embeddings.ndim != 2:
                raise ValueError("Temporal embeddings must be a 2D array")

            if embeddings.shape[0] != len(records):
                raise ValueError("Temporal embedding count must match records count")

            if self.dimension is None:
                self.dimension = int(embeddings.shape[1])

            if embeddings.shape[1] != self.dimension:
                raise ValueError(
                    "Temporal embedding dimension mismatch: "
                    f"expected={self.dimension}, got={embeddings.shape[1]}"
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
                    "start_seconds": float(record["start_seconds"]),
                    "end_seconds": float(record["end_seconds"]),
                    "thumbnail_path": str(record["thumbnail_path"]),
                }

            self.processed_videos[key] = {
                "video_filename": video_filename,
                "signature": signature,
                "frame_interval_seconds": frame_interval_seconds,
                "window_seconds": window_seconds,
                "stride_seconds": stride_seconds,
                "vector_ids": created_ids,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_locked()

            return {"status": "processed", "indexed_windows": len(created_ids)}

    def delete_video_windows(self, video_filename: str) -> dict[str, int]:
        target_filename = str(video_filename or "").strip()
        if not target_filename:
            return {"removed_vectors": 0, "removed_records": 0}

        with self._lock:
            matching_keys = [
                key
                for key, value in self.processed_videos.items()
                if str(value.get("video_filename", "")) == target_filename
            ]
            if not matching_keys:
                return {"removed_vectors": 0, "removed_records": 0}

            vector_ids: list[int] = []
            for key in matching_keys:
                item = self.processed_videos.get(key, {})
                vector_ids.extend(item.get("vector_ids", []))

            removed_vectors = len(vector_ids)
            removed_records = len(matching_keys)
            self._remove_ids_locked(vector_ids)
            for key in matching_keys:
                self.processed_videos.pop(key, None)

            self._save_locked()
            return {
                "removed_vectors": removed_vectors,
                "removed_records": removed_records,
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
                    "Temporal query dimension mismatch: "
                    f"expected={self.dimension}, got={query.shape[1]}"
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
                        "start_seconds": item["start_seconds"],
                        "end_seconds": item["end_seconds"],
                        "thumbnail_path": item["thumbnail_path"],
                        "similarity_score": float(score),
                    }
                )

            return results
