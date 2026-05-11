from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

import faiss
import numpy as np


class FaceIdentityStore:
    def __init__(
        self,
        *,
        index_path: Path,
        metadata_path: Path,
        expected_dimension: int | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.expected_dimension = int(expected_dimension) if expected_dimension else None

        self.dimension: int | None = None
        self.next_id = 0
        self.entries: dict[int, dict[str, Any]] = {}
        self.video_entries: dict[str, list[int]] = {}
        self.index: faiss.IndexIDMap2 | None = None
        self._lock = Lock()
        self._load()

    @staticmethod
    def _create_index(dimension: int) -> faiss.IndexIDMap2:
        return faiss.IndexIDMap2(faiss.IndexFlatIP(int(dimension)))

    def _load(self) -> None:
        with self._lock:
            if self.metadata_path.exists():
                payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    raw_dimension = payload.get("dimension")
                    if raw_dimension is not None:
                        self.dimension = int(raw_dimension)
                    self.next_id = max(0, int(payload.get("next_id", 0)))
                    entries = payload.get("entries", [])
                    if isinstance(entries, list):
                        for item in entries:
                            if not isinstance(item, dict):
                                continue
                            raw_id = item.get("id")
                            if raw_id is None:
                                continue
                            item_id = int(raw_id)
                            self.entries[item_id] = dict(item)
                    raw_video_entries = payload.get("video_entries", {})
                    if isinstance(raw_video_entries, dict):
                        cleaned: dict[str, list[int]] = {}
                        for raw_name, raw_ids in raw_video_entries.items():
                            if not isinstance(raw_name, str) or not isinstance(raw_ids, list):
                                continue
                            cleaned[raw_name] = [
                                int(item_id) for item_id in raw_ids if isinstance(item_id, int)
                            ]
                        self.video_entries = cleaned
                    if self.next_id <= 0 and self.entries:
                        self.next_id = max(self.entries.keys()) + 1

            if self.index_path.exists():
                loaded_index = faiss.read_index(str(self.index_path))
                if not isinstance(loaded_index, faiss.IndexIDMap2):
                    raise RuntimeError("Stored face identity index must be IndexIDMap2.")
                self.index = loaded_index
                if self.dimension is None:
                    self.dimension = int(self.index.d)

            if self.dimension is None and self.expected_dimension is not None:
                self.dimension = int(self.expected_dimension)
                self.index = self._create_index(self.dimension)

            if self.dimension is not None and self.index is None:
                self.index = self._create_index(self.dimension)

            if (
                self.expected_dimension is not None
                and self.dimension is not None
                and int(self.expected_dimension) != int(self.dimension)
            ):
                raise RuntimeError(
                    "Face identity embedding dimension mismatch: "
                    f"store={self.dimension}, model={self.expected_dimension}"
                )

    def _save_locked(self) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if self.index is not None:
            faiss.write_index(self.index, str(self.index_path))
        payload = {
            "dimension": self.dimension,
            "next_id": self.next_id,
            "entries": [self.entries[item_id] for item_id in sorted(self.entries.keys())],
            "video_entries": self.video_entries,
        }
        self.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _remove_ids_locked(self, ids: list[int]) -> None:
        if not ids or self.index is None:
            return
        ids_array = np.asarray(ids, dtype=np.int64)
        self.index.remove_ids(ids_array)
        for item_id in ids:
            self.entries.pop(int(item_id), None)

    def has_video_entries(self, video_filename: str) -> bool:
        safe_name = str(video_filename or "").strip()
        if not safe_name:
            return False
        with self._lock:
            ids = self.video_entries.get(safe_name, [])
            if not ids:
                return False
            return any(int(item_id) in self.entries for item_id in ids if isinstance(item_id, int))

    def count_video_entries(self, video_filename: str) -> int:
        safe_name = str(video_filename or "").strip()
        if not safe_name:
            return 0
        with self._lock:
            ids = self.video_entries.get(safe_name, [])
            if not isinstance(ids, list) or not ids:
                return 0
            count = 0
            for item_id in ids:
                if not isinstance(item_id, int):
                    continue
                if int(item_id) in self.entries:
                    count += 1
            return int(count)

    def counts_by_video_filename(self) -> dict[str, int]:
        with self._lock:
            output: dict[str, int] = {}
            for raw_name, raw_ids in self.video_entries.items():
                safe_name = str(raw_name or "").strip()
                if not safe_name or not isinstance(raw_ids, list):
                    continue
                count = 0
                for item_id in raw_ids:
                    if not isinstance(item_id, int):
                        continue
                    if int(item_id) in self.entries:
                        count += 1
                output[safe_name] = int(count)
            return output

    def delete_video(self, video_filename: str) -> dict[str, int]:
        safe_name = str(video_filename or "").strip()
        if not safe_name:
            return {"removed_faces": 0}
        with self._lock:
            existing_ids = list(self.video_entries.get(safe_name, []))
            if existing_ids:
                self._remove_ids_locked(existing_ids)
                self.video_entries.pop(safe_name, None)
                self._save_locked()
            return {"removed_faces": int(len(existing_ids))}

    def upsert_faces(
        self,
        *,
        video_filename: str,
        records: list[dict[str, Any]],
        embeddings: np.ndarray,
        force: bool = False,
    ) -> dict[str, Any]:
        safe_name = str(video_filename or "").strip()
        if not safe_name:
            raise ValueError("video_filename is required")

        with self._lock:
            existing_ids = list(self.video_entries.get(safe_name, []))
            has_existing = bool(existing_ids)
            if has_existing and not force:
                return {"status": "skipped", "indexed": len(existing_ids)}

            if existing_ids:
                self._remove_ids_locked(existing_ids)
                self.video_entries.pop(safe_name, None)

            embeddings = np.asarray(embeddings, dtype=np.float32)
            if embeddings.size == 0 or not records:
                self._save_locked()
                return {"status": "processed", "indexed": 0}

            if embeddings.ndim != 2:
                raise ValueError("Embeddings must be 2D")
            if embeddings.shape[0] != len(records):
                raise ValueError("Embeddings count must match records count")

            if self.dimension is None:
                self.dimension = int(embeddings.shape[1])
            if embeddings.shape[1] != int(self.dimension):
                raise ValueError(
                    "Face identity embedding dimension mismatch: "
                    f"expected={self.dimension}, got={embeddings.shape[1]}"
                )
            if self.index is None:
                self.index = self._create_index(int(self.dimension))

            ids = np.arange(self.next_id, self.next_id + embeddings.shape[0], dtype=np.int64)
            self.next_id += embeddings.shape[0]
            contiguous = np.ascontiguousarray(embeddings.astype(np.float32))
            self.index.add_with_ids(contiguous, ids)

            created_ids = ids.tolist()
            for item_id, record in zip(created_ids, records):
                self.entries[int(item_id)] = {
                    "id": int(item_id),
                    "video_filename": safe_name,
                    "timestamp_seconds": float(record.get("timestamp_seconds", 0.0)),
                    "crop_path": str(record.get("crop_path") or ""),
                    "kind": str(record.get("kind") or "face").strip().lower() or "face",
                }
            self.video_entries[safe_name] = created_ids
            self._save_locked()
            return {"status": "processed", "indexed": len(created_ids)}

    def search(
        self,
        *,
        query_embedding: np.ndarray,
        top_k: int = 100,
    ) -> list[dict[str, Any]]:
        safe_top_k = max(1, int(top_k))
        with self._lock:
            if self.index is None or self.index.ntotal == 0:
                return []

            query = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
            if self.dimension is not None and query.shape[1] != int(self.dimension):
                raise ValueError(
                    "Face identity query dimension mismatch: "
                    f"expected={self.dimension}, got={query.shape[1]}"
                )

            faiss.normalize_L2(query)
            search_pool = min(int(self.index.ntotal), max(safe_top_k, safe_top_k * 8))
            scores, ids = self.index.search(query, search_pool)

            results: list[dict[str, Any]] = []
            for score, item_id in zip(scores[0], ids[0]):
                if int(item_id) == -1:
                    continue
                entry = self.entries.get(int(item_id))
                if not entry:
                    continue
                results.append(
                    {
                        "id": int(item_id),
                        "video_filename": str(entry.get("video_filename") or ""),
                        "timestamp_seconds": float(entry.get("timestamp_seconds", 0.0)),
                        "crop_path": str(entry.get("crop_path") or ""),
                        "kind": str(entry.get("kind") or "face"),
                        "similarity_score": float(score),
                    }
                )
                if len(results) >= safe_top_k:
                    break
            return results
