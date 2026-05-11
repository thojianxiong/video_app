from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import faiss
import numpy as np


@dataclass
class _CategoryState:
    index_path: Path
    metadata_path: Path
    dimension: int | None = None
    next_id: int = 0
    entries: dict[int, dict[str, Any]] | None = None
    video_entries: dict[str, list[int]] | None = None
    index: faiss.IndexIDMap2 | None = None

    def __post_init__(self) -> None:
        if self.entries is None:
            self.entries = {}
        if self.video_entries is None:
            self.video_entries = {}


class AnalysisCropStore:
    FACE_PEOPLE = "face_people"
    VEHICLES = "vehicles"
    _VALID_CATEGORIES = {FACE_PEOPLE, VEHICLES}

    def __init__(
        self,
        *,
        face_people_index_path: Path,
        face_people_metadata_path: Path,
        vehicles_index_path: Path,
        vehicles_metadata_path: Path,
        expected_dimension: int | None = None,
    ) -> None:
        self._states: dict[str, _CategoryState] = {
            self.FACE_PEOPLE: _CategoryState(
                index_path=face_people_index_path,
                metadata_path=face_people_metadata_path,
            ),
            self.VEHICLES: _CategoryState(
                index_path=vehicles_index_path,
                metadata_path=vehicles_metadata_path,
            ),
        }
        self._lock = Lock()
        self._expected_dimension = expected_dimension
        self._load_all()

    @staticmethod
    def _create_index(dimension: int) -> faiss.IndexIDMap2:
        return faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))

    @staticmethod
    def _normalize_category(category: str) -> str:
        normalized = str(category or "").strip().lower()
        if normalized not in AnalysisCropStore._VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category}")
        return normalized

    @staticmethod
    def _normalize_kind(kind: str | None) -> str | None:
        if kind is None:
            return None
        normalized = str(kind).strip().lower()
        return normalized or None

    def _load_state(self, category: str, state: _CategoryState) -> None:
        if state.metadata_path.exists():
            payload = json.loads(state.metadata_path.read_text(encoding="utf-8"))
            state.dimension = payload.get("dimension")
            state.next_id = int(payload.get("next_id", 0))
            entries = payload.get("entries", [])
            state.entries = {
                int(item["id"]): item
                for item in entries
                if isinstance(item, dict) and "id" in item
            }
            raw_video_entries = payload.get("video_entries", {})
            if isinstance(raw_video_entries, dict):
                cleaned_video_entries: dict[str, list[int]] = {}
                for video_name, ids in raw_video_entries.items():
                    if not isinstance(video_name, str):
                        continue
                    if not isinstance(ids, list):
                        continue
                    cleaned_video_entries[video_name] = [
                        int(item_id) for item_id in ids if isinstance(item_id, int)
                    ]
                state.video_entries = cleaned_video_entries
            else:
                state.video_entries = {}

            if state.next_id <= 0 and state.entries:
                state.next_id = max(state.entries) + 1

        if state.index_path.exists():
            loaded_index = faiss.read_index(str(state.index_path))
            if not isinstance(loaded_index, faiss.IndexIDMap2):
                raise RuntimeError(f"Stored index must be IndexIDMap2 for {category}")
            state.index = loaded_index
            if state.dimension is None:
                state.dimension = int(state.index.d)

        if state.dimension is None and self._expected_dimension is not None:
            state.dimension = int(self._expected_dimension)
            state.index = self._create_index(state.dimension)

        if state.dimension is not None and state.index is None:
            state.index = self._create_index(int(state.dimension))

        if (
            self._expected_dimension is not None
            and state.dimension is not None
            and int(self._expected_dimension) != int(state.dimension)
        ):
            raise RuntimeError(
                f"Embedding dimension mismatch in {category}: "
                f"store={state.dimension}, model={self._expected_dimension}"
            )

    def _load_all(self) -> None:
        with self._lock:
            for category, state in self._states.items():
                self._load_state(category, state)

    def _save_state_locked(self, state: _CategoryState) -> None:
        state.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if state.index is not None:
            faiss.write_index(state.index, str(state.index_path))

        payload = {
            "dimension": state.dimension,
            "next_id": state.next_id,
            "entries": [state.entries[key] for key in sorted(state.entries)],
            "video_entries": state.video_entries,
        }
        state.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _remove_ids_locked(self, state: _CategoryState, ids: list[int]) -> None:
        if not ids or state.index is None:
            return
        ids_array = np.asarray(ids, dtype=np.int64)
        state.index.remove_ids(ids_array)
        for vector_id in ids:
            state.entries.pop(int(vector_id), None)

    def delete_video(self, video_filename: str) -> dict[str, int]:
        target = str(video_filename or "").strip()
        if not target:
            return {"removed_face_people": 0, "removed_vehicles": 0}

        removed_face_people = 0
        removed_vehicles = 0
        with self._lock:
            for category, state in self._states.items():
                existing_ids = list(state.video_entries.get(target, []))
                if existing_ids:
                    self._remove_ids_locked(state, existing_ids)
                    state.video_entries.pop(target, None)
                    self._save_state_locked(state)
                if category == self.FACE_PEOPLE:
                    removed_face_people = len(existing_ids)
                elif category == self.VEHICLES:
                    removed_vehicles = len(existing_ids)
        return {
            "removed_face_people": int(removed_face_people),
            "removed_vehicles": int(removed_vehicles),
        }

    def has_video_entries(self, *, category: str, video_filename: str) -> bool:
        normalized_category = self._normalize_category(category)
        target = str(video_filename or "").strip()
        if not target:
            return False
        with self._lock:
            state = self._states[normalized_category]
            ids = state.video_entries.get(target, [])
            if not isinstance(ids, list) or not ids:
                return False
            return any(int(item_id) in state.entries for item_id in ids if isinstance(item_id, int))

    def upsert_detections(
        self,
        *,
        category: str,
        video_filename: str,
        records: list[dict[str, Any]],
        embeddings: np.ndarray,
        force: bool = False,
    ) -> dict[str, Any]:
        normalized_category = self._normalize_category(category)
        target_filename = str(video_filename or "").strip()
        if not target_filename:
            raise ValueError("video_filename is required")

        with self._lock:
            state = self._states[normalized_category]
            existing_ids = list(state.video_entries.get(target_filename, []))
            has_existing = bool(existing_ids)
            if has_existing and not force:
                return {"status": "skipped", "indexed": len(existing_ids)}

            if existing_ids:
                self._remove_ids_locked(state, existing_ids)
                state.video_entries.pop(target_filename, None)

            embeddings = np.asarray(embeddings, dtype=np.float32)
            if embeddings.size == 0 or not records:
                self._save_state_locked(state)
                return {"status": "processed", "indexed": 0}

            if embeddings.ndim != 2:
                raise ValueError("Embeddings must be 2D")
            if embeddings.shape[0] != len(records):
                raise ValueError("Embeddings count must match records count")

            if state.dimension is None:
                state.dimension = int(embeddings.shape[1])
            if embeddings.shape[1] != int(state.dimension):
                raise ValueError(
                    f"Dimension mismatch in {normalized_category}: "
                    f"expected={state.dimension}, got={embeddings.shape[1]}"
                )
            if state.index is None:
                state.index = self._create_index(int(state.dimension))

            ids = np.arange(
                state.next_id,
                state.next_id + embeddings.shape[0],
                dtype=np.int64,
            )
            state.next_id += embeddings.shape[0]
            contiguous = np.ascontiguousarray(embeddings.astype(np.float32))
            state.index.add_with_ids(contiguous, ids)

            created_ids = ids.tolist()
            for vector_id, record in zip(created_ids, records):
                kind = self._normalize_kind(record.get("kind"))
                state.entries[vector_id] = {
                    "id": vector_id,
                    "video_filename": target_filename,
                    "timestamp_seconds": float(record["timestamp_seconds"]),
                    "crop_path": str(record["crop_path"]),
                    "kind": kind or "",
                }
            state.video_entries[target_filename] = created_ids
            self._save_state_locked(state)
            return {"status": "processed", "indexed": len(created_ids)}

    def list_items(
        self,
        *,
        category: str,
        limit: int = 400,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_category = self._normalize_category(category)
        normalized_kind = self._normalize_kind(kind)
        safe_limit = max(1, min(2000, int(limit)))

        with self._lock:
            state = self._states[normalized_category]
            ordered_ids = sorted(state.entries.keys(), reverse=True)
            results: list[dict[str, Any]] = []
            for vector_id in ordered_ids:
                item = state.entries.get(vector_id)
                if not item:
                    continue
                if normalized_kind and str(item.get("kind", "")).lower() != normalized_kind:
                    continue
                results.append(dict(item))
                if len(results) >= safe_limit:
                    break
            return results

    def list_video_items(
        self,
        *,
        category: str,
        video_filename: str,
        limit: int = 4000,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_category = self._normalize_category(category)
        target_video = str(video_filename or "").strip()
        normalized_kind = self._normalize_kind(kind)
        if not target_video:
            return []

        safe_limit = max(1, min(100000, int(limit)))
        with self._lock:
            state = self._states[normalized_category]
            candidate_ids = [
                int(item_id)
                for item_id in (state.video_entries.get(target_video) or [])
                if isinstance(item_id, int)
            ]
            if not candidate_ids:
                return []

            results: list[dict[str, Any]] = []
            for vector_id in sorted(candidate_ids):
                item = state.entries.get(int(vector_id))
                if not isinstance(item, dict):
                    continue
                if normalized_kind and str(item.get("kind", "")).lower() != normalized_kind:
                    continue
                results.append(dict(item))
                if len(results) >= safe_limit:
                    break
            return results

    def search(
        self,
        *,
        category: str,
        query_embedding: np.ndarray,
        top_k: int = 100,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_category = self._normalize_category(category)
        normalized_kind = self._normalize_kind(kind)
        if top_k <= 0:
            return []

        with self._lock:
            state = self._states[normalized_category]
            if state.index is None or state.index.ntotal == 0:
                return []

            query = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
            if state.dimension is not None and query.shape[1] != int(state.dimension):
                raise ValueError(
                    f"Query dimension mismatch in {normalized_category}: "
                    f"expected={state.dimension}, got={query.shape[1]}"
                )

            faiss.normalize_L2(query)
            search_pool = min(
                int(state.index.ntotal),
                max(int(top_k), int(top_k) * 8),
            )
            scores, ids = state.index.search(query, search_pool)

            results: list[dict[str, Any]] = []
            for score, vector_id in zip(scores[0], ids[0]):
                if vector_id == -1:
                    continue
                item = state.entries.get(int(vector_id))
                if not item:
                    continue
                if normalized_kind and str(item.get("kind", "")).lower() != normalized_kind:
                    continue
                results.append(
                    {
                        "id": int(vector_id),
                        "video_filename": item["video_filename"],
                        "timestamp_seconds": float(item["timestamp_seconds"]),
                        "crop_path": item["crop_path"],
                        "kind": str(item.get("kind", "")).lower(),
                        "similarity_score": float(score),
                    }
                )
                if len(results) >= int(top_k):
                    break
            return results
