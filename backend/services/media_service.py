from __future__ import annotations

import asyncio
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile


class MediaService:
    PIPELINE_STAGES = ("ingest", "normalize", "triage", "base_index", "analysis")
    QUEUE_KIND_SEMANTIC_INDEX = "semantic_index"
    QUEUE_KIND_ANALYSIS = "analysis"
    QUEUE_KIND_TRIAGE_TIMELINE = "triage_timeline"
    QUEUE_PRIORITY_SEMANTIC_INDEX = 50
    QUEUE_PRIORITY_ANALYSIS = 70
    DELETE_LOCK_CHECK_ATTEMPTS = 10
    DELETE_LOCK_CHECK_DELAY_SECONDS = 0.15
    DELETE_LOCK_CHECK_BACKOFF_MULTIPLIER = 1.6
    DELETE_LOCK_CHECK_MAX_DELAY_SECONDS = 1.0
    DELETE_PERMISSION_RETRY_ATTEMPTS = 6
    DEFAULT_UPLOAD_CHUNK_SIZE_BYTES = 8 * 1024 * 1024
    MIN_UPLOAD_CHUNK_SIZE_BYTES = 1 * 1024 * 1024
    MAX_UPLOAD_CHUNK_SIZE_BYTES = 64 * 1024 * 1024
    ANALYSIS_STATUS_CATEGORY_FACE_PEOPLE = "face_people"
    ANALYSIS_STATUS_CATEGORY_VEHICLES = "vehicles"

    def __init__(
        self,
        *,
        app: Any,
        video_extensions: set[str],
        convert_to_mp4: Any,
        generate_preview_thumbnail: Any,
        resolve_case_id_or_default: Any,
        get_case_paths_or_raise: Any,
        is_supported_video: Any,
        unique_video_path: Any,
        write_upload_file: Any,
        truncate_error: Any,
        preview_thumbnail_path: Any,
        media_url_for_case_path: Any,
        get_vector_store_for_case: Any,
        get_temporal_store_for_case: Any,
        delete_video_sync: Any,
        process_video_sync: Any,
        resolve_index_filenames: Any,
        find_running_index_case_id_locked: Any,
        new_index_job_record: Any,
        run_index_job_async: Any,
        index_job_snapshot: Any,
    ) -> None:
        self.app = app
        self.video_extensions = set(video_extensions)
        self.convert_to_mp4 = convert_to_mp4
        self.generate_preview_thumbnail = generate_preview_thumbnail
        self.resolve_case_id_or_default = resolve_case_id_or_default
        self.get_case_paths_or_raise = get_case_paths_or_raise
        self.is_supported_video = is_supported_video
        self.unique_video_path = unique_video_path
        self.write_upload_file = write_upload_file
        self.truncate_error = truncate_error
        self.preview_thumbnail_path = preview_thumbnail_path
        self.media_url_for_case_path = media_url_for_case_path
        self.get_vector_store_for_case = get_vector_store_for_case
        self.get_temporal_store_for_case = get_temporal_store_for_case
        self.delete_video_sync = delete_video_sync
        self.process_video_sync = process_video_sync
        self.resolve_index_filenames = resolve_index_filenames
        self.find_running_index_case_id_locked = find_running_index_case_id_locked
        self.new_index_job_record = new_index_job_record
        self.run_index_job_async = run_index_job_async
        self.index_job_snapshot = index_job_snapshot

    @classmethod
    def _normalize_upload_chunk_size(cls, chunk_size_bytes: int) -> int:
        raw_value = int(chunk_size_bytes or 0)
        if raw_value <= 0:
            return int(cls.DEFAULT_UPLOAD_CHUNK_SIZE_BYTES)
        return max(
            int(cls.MIN_UPLOAD_CHUNK_SIZE_BYTES),
            min(int(cls.MAX_UPLOAD_CHUNK_SIZE_BYTES), raw_value),
        )

    def _upload_session_store(self):
        return getattr(self.app.state, "upload_session_store", None)

    def _upload_session_chunk_lock(self):
        return getattr(self.app.state, "upload_session_chunk_lock", None)

    @staticmethod
    def compute_source_fingerprint_sha256(
        file_path: Path,
        *,
        sample_size_bytes: int = 1024 * 1024,
    ) -> str:
        resolved_path = Path(file_path)
        safe_sample_size = max(4096, int(sample_size_bytes))
        file_size = int(resolved_path.stat().st_size)

        hasher = hashlib.sha256()
        hasher.update(f"size:{file_size};".encode("utf-8"))

        with resolved_path.open("rb") as stream:
            head_sample = stream.read(safe_sample_size)
            if head_sample:
                hasher.update(b"head:")
                hasher.update(head_sample)

            middle_sample = b""
            if file_size > (safe_sample_size * 2):
                middle_offset = max(0, (file_size // 2) - (safe_sample_size // 2))
                stream.seek(middle_offset)
                middle_sample = stream.read(safe_sample_size)
            if middle_sample:
                hasher.update(b";middle:")
                hasher.update(middle_sample)

            tail_sample = b""
            if file_size > safe_sample_size:
                tail_size = min(safe_sample_size, file_size)
                stream.seek(max(0, file_size - tail_size))
                tail_sample = stream.read(tail_size)
            if tail_sample:
                hasher.update(b";tail:")
                hasher.update(tail_sample)

        return hasher.hexdigest()

    def _case_delete_guard(self) -> tuple[Lock, set[str]]:
        state = self.app.state
        guard_lock = getattr(state, "deleting_case_ids_lock", None)
        if guard_lock is None or not hasattr(guard_lock, "acquire"):
            guard_lock = Lock()
            setattr(state, "deleting_case_ids_lock", guard_lock)

        deleting_cases = getattr(state, "deleting_case_ids", None)
        if not isinstance(deleting_cases, set):
            deleting_cases = set()
            setattr(state, "deleting_case_ids", deleting_cases)

        # Backward compatibility for code paths still reading these keys.
        setattr(state, "case_delete_guard_lock", guard_lock)
        setattr(state, "case_delete_in_progress", deleting_cases)

        return guard_lock, deleting_cases

    def _is_case_delete_in_progress(self, case_id: str) -> bool:
        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            return False

        guard_lock, deleting_cases = self._case_delete_guard()
        with guard_lock:
            return normalized_case_id in deleting_cases

    @staticmethod
    def _default_analysis_summary() -> dict:
        return {
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
        }

    @classmethod
    def _normalize_analysis_status_category(cls, category: str | None) -> str:
        normalized = str(category or "").strip().lower()
        if not normalized:
            return ""
        if normalized in {
            cls.ANALYSIS_STATUS_CATEGORY_FACE_PEOPLE,
            cls.ANALYSIS_STATUS_CATEGORY_VEHICLES,
        }:
            return normalized
        raise HTTPException(
            status_code=400,
            detail=f"Invalid analysis category: {category}",
        )

    @staticmethod
    def _default_pipeline(case_id: str, filename: str) -> dict:
        now = ""
        return {
            "case_id": str(case_id or ""),
            "filename": str(filename or ""),
            "overall_status": "pending",
            "current_stage": "",
            "created_at": now,
            "updated_at": now,
            "last_event": "",
            "metadata": {},
            "stages": {
                "ingest": {"status": "pending"},
                "normalize": {"status": "pending"},
                "triage": {"status": "pending"},
                "base_index": {"status": "pending"},
                "analysis": {"status": "pending"},
            },
        }

    @staticmethod
    def _stage_payload(pipeline: dict, stage_name: str) -> dict:
        stages = pipeline.get("stages")
        if not isinstance(stages, dict):
            return {}
        payload = stages.get(stage_name)
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _stage_status(cls, pipeline: dict, stage_name: str) -> str:
        stage = cls._stage_payload(pipeline, stage_name)
        return str(stage.get("status") or "pending").strip().lower()

    @classmethod
    def _stage_ready(cls, pipeline: dict, stage_name: str) -> bool:
        return cls._stage_status(pipeline, stage_name) in {"completed", "skipped"}

    @classmethod
    def _pipeline_is_running(cls, pipeline: dict) -> bool:
        if str(pipeline.get("overall_status") or "").strip().lower() == "running":
            return True
        for stage_name in cls.PIPELINE_STAGES:
            if cls._stage_status(pipeline, stage_name) == "running":
                return True
        return False

    @classmethod
    def _pipeline_errors(cls, pipeline: dict) -> list[str]:
        errors: list[str] = []
        seen: set[str] = set()
        for stage_name in cls.PIPELINE_STAGES:
            stage = cls._stage_payload(pipeline, stage_name)
            if not stage:
                continue
            value = str(stage.get("error") or "").strip()
            if not value:
                continue
            entry = f"{stage_name}: {value}"
            if entry in seen:
                continue
            seen.add(entry)
            errors.append(entry)
        return errors

    @classmethod
    def _canonical_video_status(
        cls,
        *,
        pipeline: dict,
        indexed_frames: int,
        indexed_windows: int,
    ) -> str:
        pipeline_overall = str(pipeline.get("overall_status") or "").strip().lower()
        if pipeline_overall in {"failed", "interrupted"}:
            return pipeline_overall
        if cls._pipeline_is_running(pipeline):
            return "processing"
        if indexed_frames > 0 or indexed_windows > 0:
            return "ready"
        if cls._stage_ready(pipeline, "normalize"):
            return "ingested"
        if cls._stage_status(pipeline, "ingest") in {"completed", "skipped"}:
            return "uploaded"
        return "pending"

    @classmethod
    def _build_video_media_contract(
        cls,
        *,
        case_id: str,
        file_path: Path,
        video_url: str,
        preview_thumbnail_url: str,
        size_bytes: int,
        indexed_frames: int,
        indexed_windows: int,
        analysis: dict,
        pipeline: dict,
    ) -> dict:
        filename = str(file_path.name)
        extension = str(file_path.suffix.lower())
        metadata = pipeline.get("metadata")
        metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
        source_filename = str(metadata_payload.get("source_filename") or "").strip()
        stored_filename = str(metadata_payload.get("stored_filename") or filename).strip() or filename
        source_file_fingerprint_sha256 = str(
            metadata_payload.get("source_file_fingerprint_sha256") or ""
        ).strip().lower()
        try:
            source_file_size_bytes = max(0, int(metadata_payload.get("source_file_size_bytes", 0) or 0))
        except (TypeError, ValueError):
            source_file_size_bytes = 0
        analysis_face_people = (
            analysis.get("face_people") if isinstance(analysis.get("face_people"), dict) else {}
        )
        analysis_vehicles = (
            analysis.get("vehicles") if isinstance(analysis.get("vehicles"), dict) else {}
        )
        analysis_processed_frames = int(analysis.get("processed_frames", 0)) if isinstance(analysis, dict) else 0

        stage_finished_at = {}
        for stage_name in cls.PIPELINE_STAGES:
            stage_payload = cls._stage_payload(pipeline, stage_name)
            stage_finished_at[stage_name] = str(stage_payload.get("finished_at") or "").strip()

        lifecycle = {
            "ingested": cls._stage_ready(pipeline, "ingest"),
            "normalized": cls._stage_ready(pipeline, "normalize"),
            "triage_ready": cls._stage_ready(pipeline, "triage"),
            "semantic_index_ready": int(indexed_frames) > 0 or int(indexed_windows) > 0,
            "face_people_ready": bool(analysis_face_people.get("processed", False)),
            "vehicles_ready": bool(analysis_vehicles.get("processed", False)),
            "search_ready": int(indexed_frames) > 0 or int(indexed_windows) > 0,
            "playback_ready": True,
        }

        status = {
            "overall": cls._canonical_video_status(
                pipeline=pipeline,
                indexed_frames=int(indexed_frames),
                indexed_windows=int(indexed_windows),
            ),
            "pipeline": str(pipeline.get("overall_status") or "pending"),
            "current_stage": str(pipeline.get("current_stage") or ""),
            "is_running": cls._pipeline_is_running(pipeline),
        }

        if int(indexed_frames) > 0 or int(indexed_windows) > 0:
            status["indexing"] = "indexed"
        elif cls._stage_status(pipeline, "base_index") == "running":
            status["indexing"] = "running"
        else:
            status["indexing"] = "not_indexed"

        if lifecycle["face_people_ready"] or lifecycle["vehicles_ready"]:
            status["analysis"] = "partial_or_done"
            if lifecycle["face_people_ready"] and lifecycle["vehicles_ready"]:
                status["analysis"] = "done"
        elif cls._stage_status(pipeline, "analysis") == "running":
            status["analysis"] = "running"
        else:
            status["analysis"] = "not_run"

        contract = {
            "schema_version": "media_contract_v1",
            "identity": {
                "case_id": str(case_id),
                "filename": filename,
                "stored_filename": stored_filename,
                "source_filename": source_filename,
                "source_file_fingerprint_sha256": source_file_fingerprint_sha256,
                "source_file_size_bytes": int(source_file_size_bytes),
                "extension": extension,
            },
            "media": {
                "video_url": str(video_url),
                "preview_thumbnail_url": str(preview_thumbnail_url),
                "size_bytes": int(size_bytes),
            },
            "lifecycle": lifecycle,
            "status": status,
            "counts": {
                "indexed_frames": int(indexed_frames),
                "indexed_windows": int(indexed_windows),
                "analysis_processed_frames": int(analysis_processed_frames),
                "face_count": int(analysis_face_people.get("face_count", 0)),
                "people_count": int(analysis_face_people.get("people_count", 0)),
                "vehicle_count": int(analysis_vehicles.get("vehicle_count", 0)),
            },
            "timestamps": {
                "pipeline_created_at": str(pipeline.get("created_at") or ""),
                "pipeline_updated_at": str(pipeline.get("updated_at") or ""),
                "stage_finished_at": stage_finished_at,
            },
            "errors": cls._pipeline_errors(pipeline),
        }
        return contract

    @staticmethod
    def _pipeline_status_from_base(base_status: str) -> str:
        normalized = str(base_status or "").strip().lower()
        if normalized in {"processed", "completed"}:
            return "completed"
        if normalized in {"skipped", "analysis_only", "not_requested"}:
            return "skipped"
        if normalized in {"failed", "error"}:
            return "failed"
        return "completed"

    @staticmethod
    def _pipeline_status_from_analysis(analysis_status: str) -> str:
        normalized = str(analysis_status or "").strip().lower()
        if normalized in {"processed", "completed"}:
            return "completed"
        if normalized in {"skipped", "not_requested"}:
            return "skipped"
        if normalized in {"failed", "unavailable", "error"}:
            return "failed"
        return "skipped"

    @staticmethod
    def _running_pipeline_stage(snapshot: dict | None) -> str:
        if not isinstance(snapshot, dict):
            return ""

        current_stage = str(snapshot.get("current_stage") or "").strip()
        stages = snapshot.get("stages")
        if isinstance(stages, dict):
            if current_stage:
                current_payload = stages.get(current_stage)
                current_status = (
                    str(current_payload.get("status") or "").strip().lower()
                    if isinstance(current_payload, dict)
                    else ""
                )
                if current_status == "running":
                    return current_stage

            for stage_name, stage_payload in stages.items():
                if not isinstance(stage_payload, dict):
                    continue
                stage_status = str(stage_payload.get("status") or "").strip().lower()
                if stage_status == "running":
                    return str(stage_name).strip()

        overall_status = str(snapshot.get("overall_status") or "").strip().lower()
        if overall_status == "running":
            return current_stage or "unknown"
        return ""

    @staticmethod
    def _unique_filenames(items: list[str] | tuple[str, ...] | None) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for item in items or []:
            safe = Path(str(item or "")).name.strip()
            if not safe or safe in seen:
                continue
            seen.add(safe)
            output.append(safe)
        return output

    @staticmethod
    def _video_delete_key(case_id: str, filename: str) -> str:
        normalized_case_id = str(case_id or "").strip()
        safe_filename = Path(str(filename or "")).name.strip().lower()
        if not normalized_case_id or not safe_filename:
            return ""
        return f"{normalized_case_id}::{safe_filename}"

    def _video_delete_registry(self) -> tuple[Lock, set[str]]:
        state = self.app.state
        guard_lock = getattr(state, "deleting_video_keys_lock", None)
        if guard_lock is None or not hasattr(guard_lock, "acquire"):
            guard_lock = Lock()
            setattr(state, "deleting_video_keys_lock", guard_lock)

        deleting_keys = getattr(state, "deleting_video_keys", None)
        if not isinstance(deleting_keys, set):
            deleting_keys = set()
            setattr(state, "deleting_video_keys", deleting_keys)

        # Backward-compatible aliases for existing code paths.
        setattr(state, "deleting_videos_lock", guard_lock)
        setattr(state, "deleting_videos", deleting_keys)
        return guard_lock, deleting_keys

    def _is_video_delete_in_progress(self, case_id: str, filename: str) -> bool:
        key = self._video_delete_key(case_id, filename)
        if not key:
            return False
        guard_lock, deleting_keys = self._video_delete_registry()
        with guard_lock:
            return key in deleting_keys

    def _reserve_video_delete(self, case_id: str, filename: str) -> bool:
        key = self._video_delete_key(case_id, filename)
        if not key:
            return False
        guard_lock, deleting_keys = self._video_delete_registry()
        with guard_lock:
            if key in deleting_keys:
                return False
            deleting_keys.add(key)
            return True

    def _release_video_delete(self, case_id: str, filename: str) -> None:
        key = self._video_delete_key(case_id, filename)
        if not key:
            return
        guard_lock, deleting_keys = self._video_delete_registry()
        with guard_lock:
            deleting_keys.discard(key)

    def _filter_out_deleting_videos(self, *, case_id: str, filenames: list[str]) -> tuple[list[str], list[str]]:
        selected: list[str] = []
        skipped: list[str] = []
        seen: set[str] = set()
        for item in filenames:
            safe = Path(str(item or "")).name.strip()
            if not safe or safe in seen:
                continue
            seen.add(safe)
            if self._is_video_delete_in_progress(case_id, safe):
                skipped.append(safe)
                continue
            selected.append(safe)
        return selected, skipped

    @staticmethod
    def _delete_retry_delay_seconds(
        *,
        attempt_index: int,
        initial_delay_seconds: float,
        backoff_multiplier: float,
        max_delay_seconds: float,
    ) -> float:
        delay = max(0.0, float(initial_delay_seconds))
        if int(attempt_index) > 0:
            delay *= float(backoff_multiplier) ** int(attempt_index)
        return min(delay, max(0.0, float(max_delay_seconds)))

    @staticmethod
    def _is_active_status(status: str) -> bool:
        normalized = str(status or "").strip().lower()
        return normalized in {"queued", "running", "cancelling"}

    def _case_semantic_index_state(self, case_id: str) -> dict:
        normalized_case_id = str(case_id or "").strip()
        jobs = getattr(self.app.state, "index_jobs", None)
        lock = getattr(self.app.state, "index_jobs_lock", None)
        tasks = getattr(self.app.state, "index_tasks", None)
        if not isinstance(jobs, dict):
            jobs = {}
        if not isinstance(tasks, dict):
            tasks = {}

        job: dict | None = None
        task: asyncio.Task | None = None
        if lock is not None and hasattr(lock, "acquire"):
            with lock:
                payload = jobs.get(normalized_case_id)
                job = payload if isinstance(payload, dict) else None
                running_task = tasks.get(normalized_case_id)
                task = running_task if isinstance(running_task, asyncio.Task) else None
        else:
            payload = jobs.get(normalized_case_id)
            job = payload if isinstance(payload, dict) else None
            running_task = tasks.get(normalized_case_id)
            task = running_task if isinstance(running_task, asyncio.Task) else None

        status = str(job.get("status") or "").strip().lower() if isinstance(job, dict) else ""
        running = bool(job.get("running")) if isinstance(job, dict) else False
        current_filename = str(job.get("current_filename") or "").strip() if isinstance(job, dict) else ""
        filenames = (
            self._unique_filenames(job.get("filenames") or [])
            if isinstance(job, dict)
            else []
        )
        task_active = isinstance(task, asyncio.Task) and not task.done()

        return {
            "status": status,
            "running": running,
            "current_filename": current_filename,
            "filenames": filenames,
            "task_active": task_active,
            "active": running or task_active or self._is_active_status(status),
        }

    async def _get_case_active_queue_job(
        self,
        *,
        case_id: str,
        job_kind: str,
    ) -> dict | None:
        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is None or not hasattr(queue_store, "get_case_active"):
            return None

        def _load_active() -> dict | None:
            getter = getattr(queue_store, "get_case_active", None)
            if getter is None:
                return None
            try:
                return getter(case_id, job_kind=job_kind)
            except TypeError:
                return getter(case_id)

        try:
            payload = await asyncio.to_thread(_load_active)
        except Exception as exc:
            print(f"[delete-video][{case_id}] queue_lookup_failed kind={job_kind} error={exc}")
            return None
        return payload if isinstance(payload, dict) else None

    async def _list_case_active_queue_jobs_for_delete(
        self,
        *,
        case_id: str,
        filename: str,
    ) -> list[dict]:
        safe_filename = Path(str(filename or "")).name.strip()
        queue_kinds = (
            self.QUEUE_KIND_SEMANTIC_INDEX,
            self.QUEUE_KIND_ANALYSIS,
            self.QUEUE_KIND_TRIAGE_TIMELINE,
        )

        loaded = await asyncio.gather(
            *[
                self._get_case_active_queue_job(case_id=case_id, job_kind=job_kind)
                for job_kind in queue_kinds
            ]
        )

        output: list[dict] = []
        for index, payload in enumerate(loaded):
            if not isinstance(payload, dict):
                continue
            queue_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            filenames = self._unique_filenames(queue_payload.get("filenames") or [])
            status = str(payload.get("status") or "").strip().lower()
            output.append(
                {
                    "job_kind": str(payload.get("job_kind") or queue_kinds[index]).strip().lower()
                    or str(queue_kinds[index]),
                    "job_id": int(payload.get("job_id", 0)),
                    "status": status,
                    "filenames": filenames,
                    "contains_target": bool(safe_filename and safe_filename in filenames),
                }
            )
        return output

    async def _video_delete_guard_state(
        self,
        *,
        case_id: str,
        filename: str,
    ) -> dict:
        safe_filename = Path(str(filename or "")).name.strip()
        semantic_state = self._case_semantic_index_state(case_id)
        queue_jobs = await self._list_case_active_queue_jobs_for_delete(
            case_id=case_id,
            filename=safe_filename,
        )
        pipeline_snapshot = await self._pipeline_get_video_snapshot(
            case_id=case_id,
            filename=safe_filename,
        )
        running_stage = self._running_pipeline_stage(pipeline_snapshot)

        semantic_queue_job = next(
            (
                item
                for item in queue_jobs
                if str(item.get("job_kind") or "").strip().lower() == self.QUEUE_KIND_SEMANTIC_INDEX
            ),
            None,
        )
        semantic_active = bool(semantic_state.get("active", False)) or isinstance(semantic_queue_job, dict)
        semantic_targets_video = (
            str(semantic_state.get("current_filename") or "") == safe_filename
            or safe_filename in (semantic_state.get("filenames") or [])
            or bool(semantic_queue_job and semantic_queue_job.get("contains_target"))
        )

        queue_target_jobs = [
            item
            for item in queue_jobs
            if str(item.get("job_kind") or "").strip().lower() != self.QUEUE_KIND_SEMANTIC_INDEX
            and (bool(item.get("contains_target")) or not (item.get("filenames") or []))
        ]
        has_conflict = bool(semantic_active or running_stage or queue_target_jobs)
        can_cancel = bool(
            (semantic_active and semantic_targets_video)
            or queue_target_jobs
        )

        return {
            "has_conflict": has_conflict,
            "can_cancel": can_cancel,
            "semantic_active": semantic_active,
            "semantic_targets_video": semantic_targets_video,
            "semantic_status": str(semantic_state.get("status") or ""),
            "semantic_current_filename": str(semantic_state.get("current_filename") or ""),
            "semantic_filenames": self._unique_filenames(semantic_state.get("filenames") or []),
            "pipeline_running_stage": str(running_stage or "").strip(),
            "queue_jobs": queue_jobs,
            "queue_target_jobs": queue_target_jobs,
        }

    async def _cancel_semantic_for_video_delete(
        self,
        *,
        case_id: str,
        filename: str,
        force: bool,
    ) -> bool:
        normalized_case_id = str(case_id or "").strip()
        safe_filename = Path(str(filename or "")).name.strip()
        if not normalized_case_id:
            return False

        requested = False
        jobs = getattr(self.app.state, "index_jobs", None)
        tasks = getattr(self.app.state, "index_tasks", None)
        lock = getattr(self.app.state, "index_jobs_lock", None)
        now = datetime.now(timezone.utc).isoformat()
        if not isinstance(jobs, dict):
            jobs = {}
        if not isinstance(tasks, dict):
            tasks = {}

        if lock is not None and hasattr(lock, "acquire"):
            with lock:
                job = jobs.get(normalized_case_id)
                if isinstance(job, dict) and (
                    bool(job.get("running"))
                    or self._is_active_status(str(job.get("status") or ""))
                ):
                    job["cancel_requested"] = True
                    job["status"] = "cancelling"
                    job["running"] = False
                    job["updated_at"] = now
                    requested = True
                task = tasks.get(normalized_case_id)
                if bool(force) and isinstance(task, asyncio.Task) and not task.done():
                    task.cancel()
                    requested = True
        else:
            job = jobs.get(normalized_case_id)
            if isinstance(job, dict) and (
                bool(job.get("running"))
                or self._is_active_status(str(job.get("status") or ""))
            ):
                job["cancel_requested"] = True
                job["status"] = "cancelling"
                job["running"] = False
                job["updated_at"] = now
                requested = True

        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is not None and hasattr(queue_store, "cancel_case_active"):
            reason = (
                f"Cancelled because delete was requested for '{safe_filename}'."
                if safe_filename
                else "Cancelled by delete request."
            )
            try:
                cancelled = await asyncio.to_thread(
                    queue_store.cancel_case_active,
                    normalized_case_id,
                    reason=reason,
                    job_kind=self.QUEUE_KIND_SEMANTIC_INDEX,
                )
            except TypeError:
                cancelled = await asyncio.to_thread(
                    queue_store.cancel_case_active,
                    normalized_case_id,
                    reason=reason,
                )
            except Exception as exc:
                print(
                    f"[delete-video][{normalized_case_id}] semantic_cancel_failed "
                    f"file={safe_filename} error={exc}"
                )
                cancelled = 0
            if int(cancelled or 0) > 0:
                requested = True

        return requested

    async def _cancel_queue_job_kind_for_video_delete(
        self,
        *,
        case_id: str,
        filename: str,
        job_kind: str,
    ) -> bool:
        normalized_case_id = str(case_id or "").strip()
        normalized_kind = str(job_kind or "").strip().lower()
        safe_filename = Path(str(filename or "")).name.strip()
        if not normalized_case_id or not normalized_kind:
            return False
        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is None or not hasattr(queue_store, "cancel_case_active"):
            return False

        reason = (
            f"Cancelled because delete was requested for '{safe_filename}'."
            if safe_filename
            else "Cancelled by delete request."
        )
        try:
            cancelled = await asyncio.to_thread(
                queue_store.cancel_case_active,
                normalized_case_id,
                reason=reason,
                job_kind=normalized_kind,
            )
        except TypeError:
            cancelled = await asyncio.to_thread(
                queue_store.cancel_case_active,
                normalized_case_id,
                reason=reason,
            )
        except Exception as exc:
            print(
                f"[delete-video][{normalized_case_id}] queue_kind_cancel_failed "
                f"kind={normalized_kind} file={safe_filename} error={exc}"
            )
            return False

        return int(cancelled or 0) > 0

    async def _request_delete_cancellation(
        self,
        *,
        case_id: str,
        filename: str,
        guard_state: dict,
    ) -> dict:
        requested = False
        attempted = False
        safe_filename = Path(str(filename or "")).name.strip()

        if bool(guard_state.get("semantic_active")) and bool(guard_state.get("semantic_targets_video")):
            attempted = True
            force_cancel = (
                str(guard_state.get("semantic_current_filename") or "").strip()
                == safe_filename
            )
            if await self._cancel_semantic_for_video_delete(
                case_id=case_id,
                filename=safe_filename,
                force=bool(force_cancel),
            ):
                requested = True

        target_queue_jobs = guard_state.get("queue_target_jobs") or []
        if isinstance(target_queue_jobs, list):
            queue_kinds: list[str] = []
            seen: set[str] = set()
            for item in target_queue_jobs:
                if not isinstance(item, dict):
                    continue
                normalized_kind = str(item.get("job_kind") or "").strip().lower()
                if (
                    not normalized_kind
                    or normalized_kind == self.QUEUE_KIND_SEMANTIC_INDEX
                    or normalized_kind in seen
                ):
                    continue
                seen.add(normalized_kind)
                queue_kinds.append(normalized_kind)
            for queue_kind in queue_kinds:
                attempted = True
                if await self._cancel_queue_job_kind_for_video_delete(
                    case_id=case_id,
                    filename=safe_filename,
                    job_kind=queue_kind,
                ):
                    requested = True

        return {
            "attempted": bool(attempted),
            "cancel_requested": bool(requested),
        }

    def _format_delete_conflict_detail(
        self,
        *,
        case_id: str,
        filename: str,
        guard_state: dict,
        cancel_requested: bool,
    ) -> str:
        safe_filename = Path(str(filename or "")).name.strip() or str(filename or "").strip()
        normalized_case_id = str(case_id or "").strip()
        reasons: list[str] = []

        if bool(guard_state.get("semantic_active")):
            semantic_status = str(guard_state.get("semantic_status") or "").strip().lower() or "active"
            current_filename = str(guard_state.get("semantic_current_filename") or "").strip()
            if bool(guard_state.get("semantic_targets_video")):
                if current_filename and current_filename == safe_filename:
                    reasons.append(
                        f"semantic indexing is processing '{safe_filename}' (status={semantic_status})"
                    )
                else:
                    reasons.append(
                        f"semantic indexing queue includes '{safe_filename}' (status={semantic_status})"
                    )
            elif current_filename:
                reasons.append(
                    f"semantic indexing is active for this case (current file: '{current_filename}')"
                )
            else:
                reasons.append("semantic indexing is active for this case")

        running_stage = str(guard_state.get("pipeline_running_stage") or "").strip()
        if running_stage:
            reasons.append(f"pipeline stage '{running_stage}' is running for this video")

        queue_target_jobs = guard_state.get("queue_target_jobs") or []
        if isinstance(queue_target_jobs, list):
            for item in queue_target_jobs:
                if not isinstance(item, dict):
                    continue
                job_kind = str(item.get("job_kind") or "queue").strip().lower() or "queue"
                job_id = int(item.get("job_id", 0))
                status = str(item.get("status") or "").strip().lower() or "active"
                if bool(item.get("contains_target")):
                    reasons.append(
                        f"{job_kind} queue job #{job_id} references '{safe_filename}' (status={status})"
                    )
                else:
                    reasons.append(
                        f"{job_kind} queue job #{job_id} is active and still releasing resources"
                    )

        if not reasons:
            reasons.append("background processing is still active")

        prefix = (
            "Cancellation was requested, but the worker has not fully released locks yet."
            if bool(cancel_requested)
            else "Background processing is active."
        )
        return (
            f"Cannot delete '{safe_filename}' in case '{normalized_case_id}'. "
            f"{prefix} Blockers: {'; '.join(reasons)}. Retry in a few seconds."
        )

    @classmethod
    def _analysis_progress_from_snapshots(
        cls,
        *,
        filenames: list[str],
        snapshots_by_filename: dict[str, dict],
    ) -> dict:
        processed = 0
        failed = 0
        for filename in filenames:
            snapshot = snapshots_by_filename.get(filename)
            stage_status = cls._stage_status(snapshot or {}, "analysis")
            if stage_status in {"completed", "skipped", "failed"}:
                processed += 1
            if stage_status == "failed":
                failed += 1

        total = len(filenames)
        percent = (
            min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
            if total > 0
            else 0.0
        )
        return {
            "completed": int(processed),
            "total": int(total),
            "percent": float(percent),
            "failed": int(failed),
        }

    @classmethod
    def _analysis_stage_matches_category(
        cls,
        *,
        snapshot: dict,
        category: str,
    ) -> bool:
        normalized_category = cls._normalize_analysis_status_category(category)
        if not normalized_category:
            return True

        stage_payload = cls._stage_payload(snapshot, "analysis")
        details = stage_payload.get("details") if isinstance(stage_payload.get("details"), dict) else {}
        face_people_flag = bool(details.get("analysis_face_people", False))
        vehicles_flag = bool(details.get("analysis_vehicles", False))
        if not face_people_flag and not vehicles_flag:
            # Backward compatibility for older snapshots without explicit mode flags.
            return True
        if normalized_category == cls.ANALYSIS_STATUS_CATEGORY_FACE_PEOPLE:
            return face_people_flag
        if normalized_category == cls.ANALYSIS_STATUS_CATEGORY_VEHICLES:
            return vehicles_flag
        return False

    @classmethod
    def _interrupted_analysis_filenames(
        cls,
        *,
        snapshots_by_filename: dict[str, dict],
        category: str,
    ) -> list[str]:
        normalized_category = cls._normalize_analysis_status_category(category)
        output: list[str] = []
        for filename in sorted(snapshots_by_filename.keys()):
            snapshot = snapshots_by_filename.get(filename)
            if not isinstance(snapshot, dict):
                continue
            if cls._stage_status(snapshot, "analysis") != "interrupted":
                continue
            if not cls._analysis_stage_matches_category(
                snapshot=snapshot,
                category=normalized_category,
            ):
                continue
            output.append(filename)
        return output

    @classmethod
    def _recoverable_analysis_filenames(
        cls,
        *,
        filenames: list[str],
        snapshots_by_filename: dict[str, dict],
        category: str,
    ) -> list[str]:
        normalized_category = cls._normalize_analysis_status_category(category)
        recoverable_statuses = {"pending", "running", "interrupted"}
        terminal_statuses = {"completed", "skipped", "failed"}
        output: list[str] = []
        for filename in cls._unique_filenames(filenames):
            snapshot = snapshots_by_filename.get(filename)
            if not isinstance(snapshot, dict):
                # If the snapshot is missing, keep the queued payload file as recoverable.
                output.append(filename)
                continue
            if not cls._analysis_stage_matches_category(
                snapshot=snapshot,
                category=normalized_category,
            ):
                continue
            stage_status = cls._stage_status(snapshot, "analysis")
            if stage_status in terminal_statuses:
                continue
            if stage_status in recoverable_statuses:
                output.append(filename)
        return output

    @classmethod
    def _build_file_progress_rows(
        cls,
        *,
        filenames: list[str],
        snapshots_by_filename: dict[str, dict],
        stage_name: str,
        fallback_status: str = "pending",
        current_filename: str = "",
        current_processed_frames: int = 0,
        current_total_frames: int = 0,
        current_progress_percent: float = 0.0,
    ) -> list[dict]:
        safe_stage_name = str(stage_name or "").strip().lower()
        safe_fallback_status = str(fallback_status or "pending").strip().lower() or "pending"
        safe_current_filename = str(current_filename or "").strip()
        safe_current_processed = max(0, int(current_processed_frames or 0))
        safe_current_total = max(0, int(current_total_frames or 0))
        safe_current_percent = min(100.0, max(0.0, float(current_progress_percent or 0.0)))

        rows: list[dict] = []
        for filename in cls._unique_filenames(filenames):
            snapshot = snapshots_by_filename.get(filename)
            stage_payload = (
                cls._stage_payload(snapshot, safe_stage_name)
                if isinstance(snapshot, dict) and safe_stage_name
                else {}
            )
            stage_status = str(stage_payload.get("status") or "").strip().lower()
            status = stage_status or safe_fallback_status
            details = stage_payload.get("details") if isinstance(stage_payload.get("details"), dict) else {}

            processed = max(0, int(details.get("processed_frames", 0)))
            total = max(
                0,
                int(
                    details.get(
                        "estimated_total_frames",
                        details.get("total_frames", 0),
                    )
                ),
            )
            if total > 0 and total < processed:
                total = processed

            progress_percent = float(details.get("progress_percent", 0.0))
            if total > 0:
                progress_percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
            else:
                progress_percent = min(100.0, max(0.0, progress_percent))

            is_current = bool(safe_current_filename) and filename == safe_current_filename
            if is_current:
                if safe_current_processed > processed:
                    processed = safe_current_processed
                if safe_current_total > total:
                    total = safe_current_total
                if total > 0 and total < processed:
                    total = processed
                if total > 0:
                    progress_percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
                else:
                    progress_percent = max(progress_percent, safe_current_percent)

            if status in {"completed", "skipped", "failed", "interrupted"}:
                progress_percent = 100.0
            elif status == "running":
                if total > 0:
                    progress_percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
                elif is_current and safe_current_percent > 0:
                    progress_percent = safe_current_percent

            rows.append(
                {
                    "filename": filename,
                    "status": status,
                    "processed_frames": int(processed),
                    "estimated_total_frames": int(total),
                    "progress_percent": float(progress_percent),
                    "is_current": bool(is_current),
                }
            )
        return rows

    @staticmethod
    def _analysis_status_from_queue(queue_status: str, *, failed_count: int) -> str:
        normalized = str(queue_status or "").strip().lower()
        if normalized == "completed":
            if int(failed_count) > 0:
                return "completed_with_errors"
            return "completed"
        if normalized in {"queued", "running", "failed", "cancelled", "interrupted"}:
            return normalized
        return "idle"

    @staticmethod
    def _analysis_status_message(
        *,
        status: str,
        queue_error: str,
        completed: int,
        total: int,
    ) -> str:
        normalized = str(status or "").strip().lower()
        if normalized == "idle":
            return "No analysis job found for this case."
        if normalized == "queued":
            return "Background analysis is queued."
        if normalized == "running":
            if total > 0:
                return f"Background analysis is running ({completed}/{total} videos processed)."
            return "Background analysis is running."
        if normalized == "completed":
            return "Background analysis completed."
        if normalized == "completed_with_errors":
            return str(queue_error or "").strip() or "Background analysis completed with errors."
        if normalized == "failed":
            return str(queue_error or "").strip() or "Background analysis failed."
        if normalized == "cancelled":
            return str(queue_error or "").strip() or "Background analysis cancelled."
        if normalized == "interrupted":
            return str(queue_error or "").strip() or "Background analysis interrupted."
        return "Analysis status unavailable."

    @classmethod
    def _default_analysis_status_payload(cls, case_id: str) -> dict:
        return {
            "case_id": str(case_id or ""),
            "status": "idle",
            "queue": {
                "job_id": 0,
                "job_kind": cls.QUEUE_KIND_ANALYSIS,
                "priority": int(cls.QUEUE_PRIORITY_ANALYSIS),
                "status": "idle",
                "position_ahead": 0,
                "attempt_count": 0,
                "enqueued_at": "",
                "started_at": "",
                "finished_at": "",
            },
            "progress": {
                "completed": 0,
                "total": 0,
                "percent": 0.0,
            },
            "filenames": [],
            "file_progress": [],
            "analysis_face_people_filenames": [],
            "analysis_vehicles_filenames": [],
            "analysis": {
                "face_people": False,
                "vehicles": False,
            },
            "message": "No analysis job found for this case.",
        }

    def _pipeline_store(self):
        return getattr(self.app.state, "video_pipeline_store", None)

    async def _pipeline_update_stage(
        self,
        *,
        case_id: str,
        filename: str,
        stage: str,
        status: str,
        error: str = "",
        details: dict | None = None,
        increment_attempt: bool = False,
        event: str = "",
    ) -> dict | None:
        store = self._pipeline_store()
        if store is None:
            return None
        try:
            return await asyncio.to_thread(
                store.update_stage,
                case_id=case_id,
                filename=filename,
                stage=stage,
                status=status,
                error=error,
                details=details,
                increment_attempt=increment_attempt,
                event=event,
            )
        except Exception as exc:
            print(
                f"[pipeline][{case_id}] update_stage_failed file={filename} "
                f"stage={stage} status={status} error={exc}"
            )
            return None

    async def _pipeline_set_metadata(
        self,
        *,
        case_id: str,
        filename: str,
        metadata: dict,
    ) -> dict | None:
        store = self._pipeline_store()
        if store is None:
            return None
        try:
            return await asyncio.to_thread(
                store.set_metadata,
                case_id,
                filename,
                metadata,
            )
        except Exception as exc:
            print(f"[pipeline][{case_id}] metadata_failed file={filename} error={exc}")
            return None

    async def _pipeline_ensure_snapshot(self, *, case_id: str, filename: str) -> dict | None:
        store = self._pipeline_store()
        if store is None:
            return None
        try:
            return await asyncio.to_thread(store.ensure_snapshot, case_id, filename)
        except Exception as exc:
            print(f"[pipeline][{case_id}] ensure_snapshot_failed file={filename} error={exc}")
            return None

    async def _pipeline_get_video_snapshot(self, *, case_id: str, filename: str) -> dict | None:
        store = self._pipeline_store()
        if store is None:
            return None
        try:
            return await asyncio.to_thread(store.get_video_snapshot, case_id, filename)
        except Exception as exc:
            print(f"[pipeline][{case_id}] get_snapshot_failed file={filename} error={exc}")
            return None

    async def _pipeline_list_case_snapshots(self, *, case_id: str) -> list[dict]:
        store = self._pipeline_store()
        if store is None:
            return []
        try:
            payload = await asyncio.to_thread(store.list_case_snapshots, case_id)
        except Exception as exc:
            print(f"[pipeline][{case_id}] list_snapshots_failed error={exc}")
            return []
        return payload if isinstance(payload, list) else []

    async def _pipeline_delete_video(self, *, case_id: str, filename: str) -> None:
        store = self._pipeline_store()
        if store is None:
            return
        try:
            await asyncio.to_thread(store.delete_video, case_id, filename)
        except Exception as exc:
            print(f"[pipeline][{case_id}] delete_video_failed file={filename} error={exc}")

    async def _persist_index_snapshot(self, snapshot: dict) -> None:
        index_job_store = getattr(self.app.state, "index_job_store", None)
        if index_job_store is None:
            return
        try:
            await asyncio.to_thread(index_job_store.upsert_snapshot, snapshot)
        except Exception as exc:
            case_id = str(snapshot.get("case_id") or "").strip()
            print(f"[index-persist][{case_id}] failed error={exc}")

    async def _load_persisted_index_snapshot(self, case_id: str) -> dict | None:
        index_job_store = getattr(self.app.state, "index_job_store", None)
        if index_job_store is None:
            return None
        try:
            payload = await asyncio.to_thread(index_job_store.get_case_snapshot, case_id)
        except Exception as exc:
            print(f"[index-persist][{case_id}] read_failed error={exc}")
            return None
        return payload if isinstance(payload, dict) else None

    async def _finalize_uploaded_temp_file(
        self,
        *,
        case_paths: Any,
        source_filename: str,
        source_index: int,
        temp_upload_path: Path,
    ) -> dict:
        source_name = Path(str(source_filename or "")).name.strip()
        if not source_name:
            return {
                "success": False,
                "source_filename": str(source_filename or ""),
                "source_index": int(source_index),
                "stored_filename": "",
                "converted": False,
                "warning": "",
                "error": "source filename is required",
                "transcode_record": None,
                "uploaded_item": None,
            }
        if not temp_upload_path.exists() or not temp_upload_path.is_file():
            return {
                "success": False,
                "source_filename": source_name,
                "source_index": int(source_index),
                "stored_filename": "",
                "converted": False,
                "warning": "",
                "error": f"temporary upload file missing: {temp_upload_path}",
                "transcode_record": None,
                "uploaded_item": None,
            }

        temp_converted_path = case_paths.data_dir / f"converted_{uuid4().hex}.mp4"
        converted_name, converted_path = self.unique_video_path(
            case_paths.videos_dir,
            source_name,
            forced_suffix=".mp4",
        )
        pipeline_filename = str(converted_name)
        current_stage = "normalize"

        try:
            uploaded_size = int(temp_upload_path.stat().st_size) if temp_upload_path.exists() else 0
            source_fingerprint_sha256 = ""
            try:
                source_fingerprint_sha256 = await asyncio.to_thread(
                    self.compute_source_fingerprint_sha256,
                    temp_upload_path,
                )
            except Exception as fingerprint_exc:
                print(
                    f"[upload][{case_paths.case_id}] resumable fingerprint failed "
                    f"input={source_name} error={fingerprint_exc}"
                )
            await self._pipeline_ensure_snapshot(
                case_id=case_paths.case_id,
                filename=pipeline_filename,
            )
            await self._pipeline_update_stage(
                case_id=case_paths.case_id,
                filename=pipeline_filename,
                stage="ingest",
                status="completed",
                event="resumable_upload_ingest_completed",
                details={
                    "source_index": int(source_index),
                    "source_filename": source_name,
                    "uploaded_size_bytes": uploaded_size,
                },
            )
            await self._pipeline_update_stage(
                case_id=case_paths.case_id,
                filename=pipeline_filename,
                stage="normalize",
                status="running",
                increment_attempt=True,
                event="resumable_upload_normalize_started",
                details={"target_extension": ".mp4"},
            )

            print(
                f"[upload][{case_paths.case_id}] resumable convert input={source_name} "
                f"output={converted_name}"
            )
            conversion_ok, conversion_error = await asyncio.to_thread(
                self.convert_to_mp4,
                temp_upload_path,
                temp_converted_path,
            )

            if conversion_ok:
                temp_upload_path.unlink(missing_ok=True)
                await asyncio.to_thread(
                    shutil.move,
                    str(temp_converted_path),
                    str(converted_path),
                )
                preview_path = self.preview_thumbnail_path(case_paths, converted_name)
                preview_ok = await asyncio.to_thread(
                    self.generate_preview_thumbnail,
                    converted_path,
                    preview_path,
                )
                if not preview_ok:
                    print(
                        f"[upload][{case_paths.case_id}] preview generation failed "
                        f"file={converted_name}"
                    )
                await self._pipeline_update_stage(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                    stage="normalize",
                    status="completed",
                    event="resumable_upload_normalize_completed",
                    details={"converted": True, "stored_filename": converted_name},
                )
                await self._pipeline_set_metadata(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                    metadata={
                        "source_filename": source_name,
                        "stored_filename": str(converted_name),
                        "converted_to_mp4": True,
                        "source_index": int(source_index),
                        "source_file_fingerprint_sha256": source_fingerprint_sha256,
                        "source_file_size_bytes": int(uploaded_size),
                    },
                )
                print(
                    f"[upload][{case_paths.case_id}] resumable convert success input={source_name} "
                    f"output={converted_name}"
                )
                return {
                    "success": True,
                    "source_filename": source_name,
                    "source_index": int(source_index),
                    "stored_filename": str(converted_name),
                    "converted": True,
                    "warning": "",
                    "error": "",
                    "transcode_record": {
                        "source_filename": source_name,
                        "stored_filename": str(converted_name),
                    },
                    "uploaded_item": {
                        "source_index": int(source_index),
                        "source_filename": source_name,
                        "stored_filename": str(converted_name),
                        "converted": True,
                        "source_file_fingerprint_sha256": source_fingerprint_sha256,
                        "source_file_size_bytes": int(uploaded_size),
                    },
                }

            temp_converted_path.unlink(missing_ok=True)
            fallback_name, fallback_path = self.unique_video_path(
                case_paths.videos_dir,
                source_name,
            )
            if fallback_name != pipeline_filename:
                await self._pipeline_delete_video(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                )
                pipeline_filename = str(fallback_name)
                await self._pipeline_ensure_snapshot(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                )
                await self._pipeline_update_stage(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                    stage="ingest",
                    status="completed",
                    event="resumable_upload_ingest_completed_fallback",
                    details={
                        "source_index": int(source_index),
                        "source_filename": source_name,
                        "uploaded_size_bytes": uploaded_size,
                    },
                )

            await asyncio.to_thread(shutil.move, str(temp_upload_path), str(fallback_path))
            preview_path = self.preview_thumbnail_path(case_paths, fallback_name)
            preview_ok = await asyncio.to_thread(
                self.generate_preview_thumbnail,
                fallback_path,
                preview_path,
            )
            if not preview_ok:
                print(
                    f"[upload][{case_paths.case_id}] preview generation failed "
                    f"file={fallback_name}"
                )
            short_error = self.truncate_error(conversion_error)
            await self._pipeline_update_stage(
                case_id=case_paths.case_id,
                filename=pipeline_filename,
                stage="normalize",
                status="skipped",
                event="resumable_upload_normalize_fallback",
                details={
                    "converted": False,
                    "stored_filename": fallback_name,
                    "warning": short_error,
                },
            )
            await self._pipeline_set_metadata(
                case_id=case_paths.case_id,
                filename=pipeline_filename,
                metadata={
                    "source_filename": source_name,
                    "stored_filename": str(fallback_name),
                    "converted_to_mp4": False,
                    "source_index": int(source_index),
                    "source_file_fingerprint_sha256": source_fingerprint_sha256,
                    "source_file_size_bytes": int(uploaded_size),
                },
            )
            print(
                f"[upload][{case_paths.case_id}] resumable convert failure input={source_name} "
                f"output={converted_name}"
            )
            if conversion_error:
                print(f"[upload][{case_paths.case_id}] ffmpeg error: {conversion_error}")
            return {
                "success": True,
                "source_filename": source_name,
                "source_index": int(source_index),
                "stored_filename": str(fallback_name),
                "converted": False,
                "warning": f"{source_name}: mp4 conversion failed ({short_error})",
                "error": "",
                "transcode_record": None,
                "uploaded_item": {
                    "source_index": int(source_index),
                    "source_filename": source_name,
                    "stored_filename": str(fallback_name),
                    "converted": False,
                    "source_file_fingerprint_sha256": source_fingerprint_sha256,
                    "source_file_size_bytes": int(uploaded_size),
                },
            }
        except Exception as exc:
            converted_path.unlink(missing_ok=True)
            temp_converted_path.unlink(missing_ok=True)
            temp_upload_path.unlink(missing_ok=True)
            await self._pipeline_update_stage(
                case_id=case_paths.case_id,
                filename=pipeline_filename,
                stage=current_stage,
                status="failed",
                error=self.truncate_error(str(exc)),
                event="resumable_upload_stage_failed",
                details={"source_filename": source_name},
            )
            return {
                "success": False,
                "source_filename": source_name,
                "source_index": int(source_index),
                "stored_filename": "",
                "converted": False,
                "warning": "",
                "error": str(exc),
                "transcode_record": None,
                "uploaded_item": None,
            }

    async def upload(self, case_id: str | None, files: list[UploadFile]) -> dict:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        try:
            resolved_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, resolved_case_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

        uploaded: list[str] = []
        errors: list[str] = []
        transcoded: list[dict[str, str]] = []
        uploaded_items: list[dict[str, str | int | bool]] = []

        for source_index, upload_file in enumerate(files):
            if not upload_file.filename:
                errors.append("Encountered a file without a name")
                continue

            if not self.is_supported_video(upload_file.filename):
                errors.append(
                    f"{upload_file.filename}: unsupported format (allowed: "
                    + ", ".join(sorted(self.video_extensions))
                    + ")"
                )
                await upload_file.close()
                continue

            source_extension = Path(upload_file.filename).suffix.lower() or ".mp4"
            temp_upload_path = case_paths.data_dir / f"upload_{uuid4().hex}{source_extension}"
            temp_converted_path = case_paths.data_dir / f"converted_{uuid4().hex}.mp4"
            converted_name, converted_path = self.unique_video_path(
                case_paths.videos_dir,
                upload_file.filename,
                forced_suffix=".mp4",
            )
            pipeline_filename = str(converted_name)
            current_stage = "ingest"
            try:
                await self._pipeline_ensure_snapshot(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                )
                await self._pipeline_update_stage(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                    stage="ingest",
                    status="running",
                    increment_attempt=True,
                    event="upload_ingest_started",
                    details={
                        "source_index": int(source_index),
                        "source_filename": str(upload_file.filename),
                    },
                )
                await asyncio.to_thread(self.write_upload_file, upload_file, temp_upload_path)
                uploaded_size = int(temp_upload_path.stat().st_size) if temp_upload_path.exists() else 0
                source_fingerprint_sha256 = ""
                try:
                    source_fingerprint_sha256 = await asyncio.to_thread(
                        self.compute_source_fingerprint_sha256,
                        temp_upload_path,
                    )
                except Exception as fingerprint_exc:
                    print(
                        f"[upload][{case_paths.case_id}] fingerprint failed "
                        f"input={upload_file.filename} error={fingerprint_exc}"
                    )
                await self._pipeline_update_stage(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                    stage="ingest",
                    status="completed",
                    event="upload_ingest_completed",
                    details={"uploaded_size_bytes": uploaded_size},
                )

                print(
                    f"[upload][{case_paths.case_id}] convert input={upload_file.filename} "
                    f"output={converted_name}"
                )
                current_stage = "normalize"
                await self._pipeline_update_stage(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                    stage="normalize",
                    status="running",
                    increment_attempt=True,
                    event="upload_normalize_started",
                    details={"target_extension": ".mp4"},
                )
                conversion_ok, conversion_error = await asyncio.to_thread(
                    self.convert_to_mp4,
                    temp_upload_path,
                    temp_converted_path,
                )

                if conversion_ok:
                    temp_upload_path.unlink(missing_ok=True)
                    await asyncio.to_thread(
                        shutil.move,
                        str(temp_converted_path),
                        str(converted_path),
                    )
                    uploaded.append(converted_name)
                    transcoded.append(
                        {
                            "source_filename": upload_file.filename,
                            "stored_filename": converted_name,
                        }
                    )
                    uploaded_items.append(
                        {
                            "source_index": int(source_index),
                            "source_filename": str(upload_file.filename),
                            "stored_filename": str(converted_name),
                            "converted": True,
                            "source_file_fingerprint_sha256": source_fingerprint_sha256,
                            "source_file_size_bytes": int(uploaded_size),
                        }
                    )
                    preview_path = self.preview_thumbnail_path(case_paths, converted_name)
                    preview_ok = await asyncio.to_thread(
                        self.generate_preview_thumbnail,
                        converted_path,
                        preview_path,
                    )
                    if not preview_ok:
                        print(
                            f"[upload][{case_paths.case_id}] preview generation failed "
                            f"file={converted_name}"
                        )
                    print(
                        f"[upload][{case_paths.case_id}] convert success input={upload_file.filename} "
                        f"output={converted_name}"
                    )
                    await self._pipeline_update_stage(
                        case_id=case_paths.case_id,
                        filename=pipeline_filename,
                        stage="normalize",
                        status="completed",
                        event="upload_normalize_completed",
                        details={"converted": True, "stored_filename": converted_name},
                    )
                    await self._pipeline_set_metadata(
                        case_id=case_paths.case_id,
                        filename=pipeline_filename,
                        metadata={
                            "source_filename": str(upload_file.filename),
                            "stored_filename": str(converted_name),
                            "converted_to_mp4": True,
                            "source_index": int(source_index),
                            "source_file_fingerprint_sha256": source_fingerprint_sha256,
                            "source_file_size_bytes": int(uploaded_size),
                        },
                    )
                else:
                    temp_converted_path.unlink(missing_ok=True)
                    fallback_name, fallback_path = self.unique_video_path(
                        case_paths.videos_dir,
                        upload_file.filename,
                    )
                    if fallback_name != pipeline_filename:
                        await self._pipeline_delete_video(
                            case_id=case_paths.case_id,
                            filename=pipeline_filename,
                        )
                        pipeline_filename = str(fallback_name)
                        await self._pipeline_ensure_snapshot(
                            case_id=case_paths.case_id,
                            filename=pipeline_filename,
                        )
                        await self._pipeline_update_stage(
                            case_id=case_paths.case_id,
                            filename=pipeline_filename,
                            stage="ingest",
                            status="completed",
                            event="upload_ingest_completed_fallback",
                            details={
                                "source_index": int(source_index),
                                "source_filename": str(upload_file.filename),
                            },
                        )
                    await asyncio.to_thread(shutil.move, str(temp_upload_path), str(fallback_path))
                    uploaded.append(fallback_name)
                    uploaded_items.append(
                        {
                            "source_index": int(source_index),
                            "source_filename": str(upload_file.filename),
                            "stored_filename": str(fallback_name),
                            "converted": False,
                            "source_file_fingerprint_sha256": source_fingerprint_sha256,
                            "source_file_size_bytes": int(uploaded_size),
                        }
                    )
                    preview_path = self.preview_thumbnail_path(case_paths, fallback_name)
                    preview_ok = await asyncio.to_thread(
                        self.generate_preview_thumbnail,
                        fallback_path,
                        preview_path,
                    )
                    if not preview_ok:
                        print(
                            f"[upload][{case_paths.case_id}] preview generation failed "
                            f"file={fallback_name}"
                        )
                    short_error = self.truncate_error(conversion_error)
                    errors.append(
                        f"{upload_file.filename}: mp4 conversion failed ({short_error})"
                    )
                    await self._pipeline_update_stage(
                        case_id=case_paths.case_id,
                        filename=pipeline_filename,
                        stage="normalize",
                        status="skipped",
                        event="upload_normalize_fallback",
                        details={
                            "converted": False,
                            "stored_filename": fallback_name,
                            "warning": short_error,
                        },
                    )
                    await self._pipeline_set_metadata(
                        case_id=case_paths.case_id,
                        filename=pipeline_filename,
                        metadata={
                            "source_filename": str(upload_file.filename),
                            "stored_filename": str(fallback_name),
                            "converted_to_mp4": False,
                            "source_index": int(source_index),
                            "source_file_fingerprint_sha256": source_fingerprint_sha256,
                            "source_file_size_bytes": int(uploaded_size),
                        },
                    )
                    print(
                        f"[upload][{case_paths.case_id}] convert failure input={upload_file.filename} "
                        f"output={converted_name}"
                    )
                    if conversion_error:
                        print(f"[upload][{case_paths.case_id}] ffmpeg error: {conversion_error}")
            except Exception as exc:
                converted_path.unlink(missing_ok=True)
                temp_converted_path.unlink(missing_ok=True)
                temp_upload_path.unlink(missing_ok=True)
                errors.append(f"{upload_file.filename}: {exc}")
                await self._pipeline_update_stage(
                    case_id=case_paths.case_id,
                    filename=pipeline_filename,
                    stage=current_stage,
                    status="failed",
                    error=self.truncate_error(str(exc)),
                    event="upload_stage_failed",
                    details={"source_filename": str(upload_file.filename)},
                )
            finally:
                await upload_file.close()

        return {
            "case_id": case_paths.case_id,
            "uploaded": uploaded,
            "uploaded_items": uploaded_items,
            "errors": errors,
            "transcoded": transcoded,
        }

    async def start_upload_session(
        self,
        *,
        case_id: str | None,
        files: list[Any],
        chunk_size_bytes: int,
    ) -> dict:
        if not isinstance(files, list) or not files:
            raise HTTPException(status_code=400, detail="No files provided")

        try:
            resolved_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, resolved_case_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

        upload_session_store = self._upload_session_store()
        if upload_session_store is None:
            raise HTTPException(status_code=500, detail="Upload session store unavailable")

        normalized_chunk_size = self._normalize_upload_chunk_size(chunk_size_bytes)
        session_id = str(uuid4())
        file_specs: list[dict[str, Any]] = []

        try:
            for fallback_index, item in enumerate(files):
                source_index = max(0, int(getattr(item, "source_index", fallback_index)))
                source_filename = Path(str(getattr(item, "source_filename", ""))).name.strip()
                source_size = max(0, int(getattr(item, "source_size", 0)))
                source_last_modified_ms = max(0, int(getattr(item, "source_last_modified_ms", 0) or 0))
                source_key = str(getattr(item, "source_key", "")).strip()
                if not source_filename:
                    raise ValueError(f"Invalid source filename for item at index {fallback_index}")
                if not self.is_supported_video(source_filename):
                    raise ValueError(
                        f"{source_filename}: unsupported format (allowed: "
                        + ", ".join(sorted(self.video_extensions))
                        + ")"
                    )
                if not source_key:
                    source_key = f"{source_filename}::{source_size}::{source_last_modified_ms}"
                source_extension = Path(source_filename).suffix.lower() or ".mp4"
                file_id = str(uuid4())
                temp_upload_path = (
                    case_paths.data_dir
                    / f"upload_session_{session_id}_{source_index}_{uuid4().hex}{source_extension}"
                )
                await asyncio.to_thread(temp_upload_path.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(temp_upload_path.touch, exist_ok=True)
                file_specs.append(
                    {
                        "file_id": file_id,
                        "source_index": source_index,
                        "source_filename": source_filename,
                        "source_size": source_size,
                        "source_last_modified_ms": source_last_modified_ms,
                        "source_key": source_key,
                        "source_extension": source_extension,
                        "temp_upload_path": str(temp_upload_path),
                    }
                )
        except ValueError as exc:
            # Best effort cleanup if session creation did not happen.
            for item in file_specs:
                try:
                    Path(str(item.get("temp_upload_path") or "")).unlink(missing_ok=True)
                except Exception:
                    pass
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            # Best effort cleanup if session creation did not happen.
            for item in file_specs:
                try:
                    Path(str(item.get("temp_upload_path") or "")).unlink(missing_ok=True)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=str(exc))

        try:
            session_payload = await asyncio.to_thread(
                upload_session_store.create_session,
                session_id=session_id,
                case_id=resolved_case_id,
                chunk_size_bytes=normalized_chunk_size,
                files=file_specs,
            )
        except ValueError as exc:
            for item in file_specs:
                try:
                    Path(str(item.get("temp_upload_path") or "")).unlink(missing_ok=True)
                except Exception:
                    pass
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            for item in file_specs:
                try:
                    Path(str(item.get("temp_upload_path") or "")).unlink(missing_ok=True)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=str(exc))

        print(
            f"[upload-session][{resolved_case_id}] started session_id={session_id} "
            f"files={len(file_specs)} chunk_size={normalized_chunk_size}"
        )
        return session_payload

    async def get_upload_session_status(self, *, session_id: str) -> dict:
        upload_session_store = self._upload_session_store()
        if upload_session_store is None:
            raise HTTPException(status_code=500, detail="Upload session store unavailable")
        try:
            payload = await asyncio.to_thread(upload_session_store.get_session, session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        if not isinstance(payload, dict):
            raise HTTPException(status_code=404, detail=f"Upload session not found: {session_id}")
        return payload

    async def upload_session_chunk(
        self,
        *,
        session_id: str,
        file_id: str,
        chunk_index: int,
        total_chunks: int,
        chunk_bytes: bytes,
    ) -> dict:
        upload_session_store = self._upload_session_store()
        if upload_session_store is None:
            raise HTTPException(status_code=500, detail="Upload session store unavailable")

        normalized_chunk_bytes = bytes(chunk_bytes or b"")
        normalized_chunk_index = max(0, int(chunk_index))
        normalized_total_chunks = max(1, int(total_chunks))
        chunk_lock = self._upload_session_chunk_lock()

        def _write_chunk_sync() -> dict:
            lock_obj = chunk_lock if chunk_lock is not None and hasattr(chunk_lock, "acquire") else None
            if lock_obj is not None:
                lock_obj.acquire()
            try:
                session_payload = upload_session_store.get_session(session_id)
                if not isinstance(session_payload, dict):
                    raise KeyError(f"Upload session not found: {session_id}")
                session_status = str(session_payload.get("status") or "")
                if session_status not in {"active"}:
                    raise ValueError(
                        f"Upload session {session_id} is not active (status={session_status})."
                    )

                file_payload = upload_session_store.get_session_file(session_id, file_id)
                if not isinstance(file_payload, dict):
                    raise KeyError(f"Upload session file not found: {file_id}")
                file_status = str(file_payload.get("status") or "")
                if file_status in {"completed", "failed", "cancelled"}:
                    return {
                        "already_received": True,
                        "file": file_payload,
                        "session": session_payload,
                    }

                file_total_chunks = max(
                    int(file_payload.get("total_chunks", 1)),
                    normalized_total_chunks,
                )
                if normalized_chunk_index >= file_total_chunks:
                    raise ValueError(
                        f"chunk_index {normalized_chunk_index} out of range for file {file_id}"
                    )

                if upload_session_store.has_chunk(file_id, normalized_chunk_index):
                    latest_file = upload_session_store.get_session_file(session_id, file_id)
                    latest_session = upload_session_store.get_session(session_id)
                    return {
                        "already_received": True,
                        "file": latest_file,
                        "session": latest_session,
                    }

                source_size = max(0, int(file_payload.get("source_size", 0)))
                chunk_size_bytes = max(1, int(file_payload.get("chunk_size_bytes", 1)))
                start_offset = normalized_chunk_index * chunk_size_bytes
                if source_size > 0 and start_offset > source_size:
                    raise ValueError(
                        f"chunk_index {normalized_chunk_index} offset is beyond file size"
                    )
                if len(normalized_chunk_bytes) > chunk_size_bytes:
                    raise ValueError(
                        f"chunk payload too large: {len(normalized_chunk_bytes)} > {chunk_size_bytes}"
                    )
                if source_size == 0:
                    if len(normalized_chunk_bytes) > 0:
                        raise ValueError("chunk payload must be empty for zero-byte source file")
                else:
                    max_payload = max(0, source_size - start_offset)
                    if len(normalized_chunk_bytes) > max_payload:
                        raise ValueError(
                            f"chunk payload exceeds remaining bytes ({len(normalized_chunk_bytes)} > {max_payload})"
                        )

                temp_upload_path = Path(str(file_payload.get("temp_upload_path") or ""))
                if not str(temp_upload_path):
                    raise ValueError("missing temporary upload path")
                temp_upload_path.parent.mkdir(parents=True, exist_ok=True)
                if temp_upload_path.exists():
                    mode = "r+b"
                else:
                    mode = "wb+"
                with temp_upload_path.open(mode) as stream:
                    stream.seek(start_offset)
                    if normalized_chunk_bytes:
                        stream.write(normalized_chunk_bytes)
                    stream.flush()

                record_payload = upload_session_store.record_chunk(
                    session_id=session_id,
                    file_id=file_id,
                    chunk_index=normalized_chunk_index,
                    chunk_size_bytes=len(normalized_chunk_bytes),
                    total_chunks=file_total_chunks,
                )
                return {
                    "already_received": False,
                    "file": record_payload.get("file"),
                    "session": record_payload.get("session"),
                }
            finally:
                if lock_obj is not None:
                    lock_obj.release()

        try:
            result = await asyncio.to_thread(_write_chunk_sync)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        file_payload = result.get("file") if isinstance(result, dict) else None
        session_payload = result.get("session") if isinstance(result, dict) else None
        return {
            "session_id": str(session_id),
            "file_id": str(file_id),
            "chunk_index": normalized_chunk_index,
            "already_received": bool(result.get("already_received")) if isinstance(result, dict) else False,
            "file": file_payload if isinstance(file_payload, dict) else {},
            "session": session_payload if isinstance(session_payload, dict) else {},
        }

    async def complete_upload_session(self, *, session_id: str) -> dict:
        upload_session_store = self._upload_session_store()
        if upload_session_store is None:
            raise HTTPException(status_code=500, detail="Upload session store unavailable")

        try:
            initial_session = await asyncio.to_thread(upload_session_store.get_session, session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        if not isinstance(initial_session, dict):
            raise HTTPException(status_code=404, detail=f"Upload session not found: {session_id}")

        session_status = str(initial_session.get("status") or "")
        if session_status not in {"active", "completed", "completed_with_errors"}:
            raise HTTPException(
                status_code=409,
                detail=f"Upload session {session_id} is not in a completable state (status={session_status}).",
            )

        case_id = str(initial_session.get("case_id") or "").strip()
        if not case_id:
            raise HTTPException(status_code=500, detail="Upload session is missing case_id")
        try:
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, case_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        uploaded: list[str] = []
        errors: list[str] = []
        transcoded: list[dict[str, str]] = []
        uploaded_items: list[dict[str, str | int | bool]] = []

        files = initial_session.get("files")
        file_list = files if isinstance(files, list) else []
        if not file_list:
            raise HTTPException(status_code=400, detail="Upload session has no files")

        for item in file_list:
            file_id = str(item.get("file_id") or "").strip()
            source_filename = str(item.get("source_filename") or "").strip()
            source_index = max(0, int(item.get("source_index", 0)))
            source_size = max(0, int(item.get("source_size", 0)))
            received_bytes = max(0, int(item.get("received_bytes", 0)))
            total_chunks = max(1, int(item.get("total_chunks", 1)))
            received_chunks = max(0, int(item.get("received_chunks", 0)))
            file_status = str(item.get("status") or "")
            uploaded_filename_existing = str(item.get("uploaded_filename") or "").strip()
            converted_existing = bool(item.get("converted_to_mp4"))
            file_error = str(item.get("error") or "").strip()
            temp_upload_path = Path(str(item.get("temp_upload_path") or ""))

            if file_status == "completed" and uploaded_filename_existing:
                uploaded.append(uploaded_filename_existing)
                uploaded_items.append(
                    {
                        "source_index": source_index,
                        "source_filename": source_filename,
                        "stored_filename": uploaded_filename_existing,
                        "converted": converted_existing,
                    }
                )
                if converted_existing:
                    transcoded.append(
                        {
                            "source_filename": source_filename,
                            "stored_filename": uploaded_filename_existing,
                        }
                    )
                continue
            if file_status == "failed":
                errors.append(
                    f"{source_filename}: {file_error or 'upload session file already marked as failed'}"
                )
                continue

            if received_chunks < total_chunks or (source_size > 0 and received_bytes < source_size):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"File is not fully uploaded yet: {source_filename} "
                        f"({received_chunks}/{total_chunks} chunks, {received_bytes}/{source_size} bytes)"
                    ),
                )

            finalize_payload = await self._finalize_uploaded_temp_file(
                case_paths=case_paths,
                source_filename=source_filename,
                source_index=source_index,
                temp_upload_path=temp_upload_path,
            )
            finalize_success = bool(finalize_payload.get("success"))
            finalize_error = str(finalize_payload.get("error") or "").strip()
            finalize_warning = str(finalize_payload.get("warning") or "").strip()
            stored_filename = str(finalize_payload.get("stored_filename") or "").strip()
            converted_to_mp4 = bool(finalize_payload.get("converted"))

            if finalize_success and stored_filename:
                uploaded.append(stored_filename)
                uploaded_item = finalize_payload.get("uploaded_item")
                if isinstance(uploaded_item, dict):
                    uploaded_items.append(uploaded_item)
                else:
                    uploaded_items.append(
                        {
                            "source_index": source_index,
                            "source_filename": source_filename,
                            "stored_filename": stored_filename,
                            "converted": converted_to_mp4,
                        }
                    )
                transcode_record = finalize_payload.get("transcode_record")
                if isinstance(transcode_record, dict):
                    transcoded.append(transcode_record)
                if finalize_warning:
                    errors.append(finalize_warning)
                try:
                    await asyncio.to_thread(
                        upload_session_store.update_file_status,
                        session_id=session_id,
                        file_id=file_id,
                        status="completed",
                        uploaded_filename=stored_filename,
                        converted_to_mp4=converted_to_mp4,
                        error="",
                    )
                except Exception as exc:
                    errors.append(f"{source_filename}: session state update failed ({exc})")
                continue

            failure_message = finalize_error or "failed to finalize uploaded file"
            errors.append(f"{source_filename}: {failure_message}")
            try:
                await asyncio.to_thread(
                    upload_session_store.update_file_status,
                    session_id=session_id,
                    file_id=file_id,
                    status="failed",
                    uploaded_filename="",
                    converted_to_mp4=False,
                    error=failure_message,
                )
            except Exception:
                pass

        completion_status = "completed_with_errors" if errors else "completed"
        try:
            final_session = await asyncio.to_thread(
                upload_session_store.update_session_status,
                session_id=session_id,
                status=completion_status,
                error=" | ".join(errors[:3]) if errors else "",
            )
        except Exception:
            final_session = await asyncio.to_thread(upload_session_store.get_session, session_id)

        return {
            "case_id": case_id,
            "session_id": str(session_id),
            "uploaded": uploaded,
            "uploaded_items": uploaded_items,
            "errors": errors,
            "transcoded": transcoded,
            "session": final_session if isinstance(final_session, dict) else {},
        }

    async def list_videos(self, case_id: str | None) -> dict:
        try:
            resolved_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            case_paths, vector_store = await asyncio.to_thread(
                self.get_vector_store_for_case,
                resolved_case_id,
            )
            _, temporal_store = await asyncio.to_thread(
                self.get_temporal_store_for_case,
                resolved_case_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

        indexed_counts = vector_store.indexed_counts_by_filename()
        indexed_window_counts = temporal_store.indexed_counts_by_filename()
        preview_thumbnails = vector_store.preview_thumbnails_by_filename()
        analysis_summary = vector_store.analysis_summary_by_filename()
        pipeline_snapshots = await self._pipeline_list_case_snapshots(case_id=case_paths.case_id)
        pipeline_by_filename = {}
        for item in pipeline_snapshots:
            if not isinstance(item, dict):
                continue
            filename_key = str(item.get("filename") or "").strip()
            if not filename_key:
                continue
            pipeline_by_filename[filename_key] = item
        videos = []

        for file_path in sorted(case_paths.videos_dir.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.video_extensions:
                continue

            file_stat = file_path.stat()
            preview_url = str(preview_thumbnails.get(file_path.name, "")).strip()
            if not preview_url:
                preview_path = self.preview_thumbnail_path(case_paths, file_path.name)
                if not preview_path.exists():
                    try:
                        await asyncio.to_thread(
                            self.generate_preview_thumbnail,
                            file_path,
                            preview_path,
                        )
                    except Exception:
                        pass
                if preview_path.exists():
                    preview_url = self.media_url_for_case_path(preview_path)

            indexed_frames = int(indexed_counts.get(file_path.name, 0))
            indexed_windows = int(indexed_window_counts.get(file_path.name, 0))
            analysis = analysis_summary.get(
                file_path.name,
                self._default_analysis_summary(),
            )
            pipeline = pipeline_by_filename.get(
                file_path.name,
                self._default_pipeline(case_paths.case_id, file_path.name),
            )
            video_url = self.media_url_for_case_path(file_path)

            videos.append(
                {
                    "filename": file_path.name,
                    "size_bytes": file_stat.st_size,
                    "video_url": video_url,
                    "preview_thumbnail_url": preview_url,
                    "indexed_frames": indexed_frames,
                    "indexed_windows": indexed_windows,
                    "analysis": analysis,
                    "pipeline": pipeline,
                    "media_contract": self._build_video_media_contract(
                        case_id=case_paths.case_id,
                        file_path=file_path,
                        video_url=video_url,
                        preview_thumbnail_url=preview_url,
                        size_bytes=int(file_stat.st_size),
                        indexed_frames=indexed_frames,
                        indexed_windows=indexed_windows,
                        analysis=analysis,
                        pipeline=pipeline,
                    ),
                }
            )

        return {
            "case_id": case_paths.case_id,
            "videos": videos,
            "contracts": {
                "media_contract": "media_contract_v1",
            },
        }

    async def delete_video(self, case_id: str | None, filename: str | None) -> dict:
        if not filename or not str(filename).strip():
            raise HTTPException(status_code=400, detail="filename is required")

        resolved_case_id = ""
        reservation_acquired = False
        safe_filename = Path(str(filename or "")).name.strip()
        try:
            resolved_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            if not safe_filename:
                raise HTTPException(status_code=400, detail="filename is required")
            if self._is_case_delete_in_progress(resolved_case_id):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Case {resolved_case_id} is being deleted. "
                        "Wait for deletion to finish, then retry."
                    ),
                )
            reservation_acquired = self._reserve_video_delete(resolved_case_id, safe_filename)
            if not reservation_acquired:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Delete already in progress for '{safe_filename}' in case '{resolved_case_id}'. "
                        "Wait for the ongoing delete operation to finish, then retry."
                    ),
                )

            guard_attempts = max(1, int(self.DELETE_LOCK_CHECK_ATTEMPTS))
            guard_state: dict = {}
            cancel_requested = False
            for attempt_index in range(guard_attempts):
                guard_state = await self._video_delete_guard_state(
                    case_id=resolved_case_id,
                    filename=safe_filename,
                )
                if not bool(guard_state.get("has_conflict")):
                    break

                can_cancel = bool(guard_state.get("can_cancel"))
                if can_cancel:
                    cancel_payload = await self._request_delete_cancellation(
                        case_id=resolved_case_id,
                        filename=safe_filename,
                        guard_state=guard_state,
                    )
                    if isinstance(cancel_payload, dict):
                        cancel_requested = (
                            bool(cancel_payload.get("cancel_requested", False))
                            or bool(cancel_requested)
                        )

                if attempt_index >= guard_attempts - 1:
                    break

                delay = self._delete_retry_delay_seconds(
                    attempt_index=attempt_index,
                    initial_delay_seconds=float(self.DELETE_LOCK_CHECK_DELAY_SECONDS),
                    backoff_multiplier=float(self.DELETE_LOCK_CHECK_BACKOFF_MULTIPLIER),
                    max_delay_seconds=float(self.DELETE_LOCK_CHECK_MAX_DELAY_SECONDS),
                )
                if delay > 0:
                    await asyncio.sleep(delay)

            if bool(guard_state.get("has_conflict")):
                raise HTTPException(
                    status_code=409,
                    detail=self._format_delete_conflict_detail(
                        case_id=resolved_case_id,
                        filename=safe_filename,
                        guard_state=guard_state,
                        cancel_requested=bool(cancel_requested),
                    ),
                )

            payload: dict | None = None
            last_permission_error: PermissionError | None = None
            delete_attempts = max(1, int(self.DELETE_PERMISSION_RETRY_ATTEMPTS))
            for attempt_index in range(delete_attempts):
                try:
                    payload = await asyncio.to_thread(
                        self.delete_video_sync,
                        resolved_case_id,
                        safe_filename,
                    )
                    break
                except PermissionError as exc:
                    last_permission_error = exc
                    guard_state = await self._video_delete_guard_state(
                        case_id=resolved_case_id,
                        filename=safe_filename,
                    )
                    if bool(guard_state.get("has_conflict")):
                        raise HTTPException(
                            status_code=409,
                            detail=self._format_delete_conflict_detail(
                                case_id=resolved_case_id,
                                filename=safe_filename,
                                guard_state=guard_state,
                                cancel_requested=bool(cancel_requested),
                            ),
                        )
                    if attempt_index >= delete_attempts - 1:
                        break
                    delay = self._delete_retry_delay_seconds(
                        attempt_index=attempt_index,
                        initial_delay_seconds=float(self.DELETE_LOCK_CHECK_DELAY_SECONDS),
                        backoff_multiplier=float(self.DELETE_LOCK_CHECK_BACKOFF_MULTIPLIER),
                        max_delay_seconds=float(self.DELETE_LOCK_CHECK_MAX_DELAY_SECONDS),
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)

            if payload is None:
                if last_permission_error is not None:
                    raise last_permission_error
                raise RuntimeError(f"Failed to delete video: {safe_filename}")

            await self._pipeline_delete_video(case_id=resolved_case_id, filename=safe_filename)
            return payload
        except HTTPException:
            raise
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Video not found: {filename}")
        except PermissionError as exc:
            target_name = safe_filename or Path(str(filename or "")).name.strip() or str(filename or "")
            case_hint = resolved_case_id or str(case_id or "").strip()
            clean_error = str(exc or "").strip()
            if clean_error:
                detail = f"Failed to delete '{target_name}' in case '{case_hint}'. {clean_error}"
            else:
                detail = (
                    f"Failed to delete '{target_name}' in case '{case_hint}' because the file is still in use."
                )
            raise HTTPException(status_code=409, detail=detail)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        finally:
            if reservation_acquired and resolved_case_id and safe_filename:
                self._release_video_delete(resolved_case_id, safe_filename)

    async def process_video(
        self,
        *,
        case_id: str | None,
        filename: str,
        frame_interval_seconds: float,
        batch_size: int,
        force: bool,
        analysis_face_people: bool,
        analysis_vehicles: bool,
        analysis_only: bool,
    ) -> dict:
        resolved_case_id = ""
        base_stage_started = False
        analysis_stage_started = False
        pipeline_filename = Path(str(filename or "")).name.strip() or str(filename or "").strip()
        try:
            resolved_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            if not pipeline_filename:
                raise ValueError("filename is required")

            await self._pipeline_ensure_snapshot(
                case_id=resolved_case_id,
                filename=pipeline_filename,
            )
            await self._pipeline_set_metadata(
                case_id=resolved_case_id,
                filename=pipeline_filename,
                metadata={
                    "requested_filename": str(filename),
                    "frame_interval_seconds": float(frame_interval_seconds),
                    "batch_size": int(batch_size),
                    "force": bool(force),
                    "analysis_only": bool(analysis_only),
                },
            )

            if analysis_only:
                await self._pipeline_update_stage(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                    stage="base_index",
                    status="skipped",
                    event="manual_process_analysis_only",
                    details={"reason": "analysis_only"},
                )
            else:
                await self._pipeline_update_stage(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                    stage="base_index",
                    status="running",
                    increment_attempt=True,
                    event="manual_process_base_index_started",
                    details={"force": bool(force)},
                )
                base_stage_started = True

            if analysis_face_people or analysis_vehicles:
                await self._pipeline_update_stage(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                    stage="analysis",
                    status="running",
                    increment_attempt=True,
                    event="manual_process_analysis_started",
                    details={
                        "face_people": bool(analysis_face_people),
                        "vehicles": bool(analysis_vehicles),
                    },
                )
                analysis_stage_started = True
            else:
                await self._pipeline_update_stage(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                    stage="analysis",
                    status="skipped",
                    event="manual_process_analysis_not_requested",
                    details={"reason": "analysis not requested"},
                )

            payload = await asyncio.to_thread(
                self.process_video_sync,
                case_id=resolved_case_id,
                filename=filename,
                frame_interval_seconds=frame_interval_seconds,
                batch_size=batch_size,
                force=force,
                analysis_face_people=analysis_face_people,
                analysis_vehicles=analysis_vehicles,
                analysis_only=analysis_only,
            )
            resolved_output_filename = (
                Path(str(payload.get("video_filename") or pipeline_filename)).name.strip()
                or pipeline_filename
            )
            if resolved_output_filename != pipeline_filename:
                await self._pipeline_delete_video(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                )
                pipeline_filename = resolved_output_filename
                await self._pipeline_ensure_snapshot(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                )

            base_status = self._pipeline_status_from_base(str(payload.get("status") or ""))
            if analysis_only and base_status == "completed":
                base_status = "skipped"
            await self._pipeline_update_stage(
                case_id=resolved_case_id,
                filename=pipeline_filename,
                stage="base_index",
                status=base_status,
                event=f"manual_process_base_index_{base_status}",
                details={
                    "result_status": str(payload.get("status") or ""),
                    "indexed_frames": int(payload.get("indexed_frames", 0)),
                    "indexed_windows": int(payload.get("indexed_windows", 0)),
                    "processed_frames": int(payload.get("processed_frames", 0)),
                },
            )

            analysis_payload = payload.get("analysis")
            if isinstance(analysis_payload, dict):
                analysis_status = self._pipeline_status_from_analysis(
                    str(analysis_payload.get("status") or "not_requested")
                )
                await self._pipeline_update_stage(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                    stage="analysis",
                    status=analysis_status,
                    event=f"manual_process_analysis_{analysis_status}",
                    details={
                        "result_status": str(analysis_payload.get("status") or ""),
                        "ran": bool(analysis_payload.get("ran", False)),
                        "pending": dict(analysis_payload.get("pending") or {}),
                        "requested": dict(analysis_payload.get("requested") or {}),
                    },
                )

            await self._pipeline_set_metadata(
                case_id=resolved_case_id,
                filename=pipeline_filename,
                metadata={
                    "stored_filename": str(payload.get("video_filename") or pipeline_filename),
                    "last_process_at": str(payload.get("updated_at") or ""),
                },
            )
            return payload
        except FileNotFoundError:
            if resolved_case_id and base_stage_started:
                await self._pipeline_update_stage(
                    case_id=resolved_case_id,
                    filename=pipeline_filename,
                    stage="base_index",
                    status="failed",
                    error="Video file not found",
                    event="manual_process_base_index_failed",
                )
            raise HTTPException(
                status_code=404,
                detail=f"Video not found: {filename}",
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            fallback_case_id = resolved_case_id or str(case_id or "").strip()
            if fallback_case_id and base_stage_started:
                await self._pipeline_update_stage(
                    case_id=fallback_case_id,
                    filename=pipeline_filename,
                    stage="base_index",
                    status="failed",
                    error=self.truncate_error(str(exc)),
                    event="manual_process_base_index_failed",
                )
            if fallback_case_id and analysis_stage_started:
                await self._pipeline_update_stage(
                    case_id=fallback_case_id,
                    filename=pipeline_filename,
                    stage="analysis",
                    status="failed",
                    error=self.truncate_error(str(exc)),
                    event="manual_process_analysis_failed",
                )
            raise HTTPException(status_code=500, detail=str(exc))

    async def start_background_index(
        self,
        *,
        case_id: str | None,
        filenames: list[str] | None,
        frame_interval_seconds: float,
        batch_size: int,
        force: bool,
    ) -> dict:
        locked_filenames: list[str] = []
        try:
            resolved_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            if self._is_case_delete_in_progress(resolved_case_id):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Case {resolved_case_id} is being deleted. "
                        "Wait for deletion to finish, then retry."
                    ),
                )
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, resolved_case_id)
            resolved_filenames = await asyncio.to_thread(
                self.resolve_index_filenames,
                case_paths,
                filenames,
            )
            resolved_filenames, locked_filenames = self._filter_out_deleting_videos(
                case_id=resolved_case_id,
                filenames=resolved_filenames,
            )
            if not resolved_filenames:
                if locked_filenames:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "All requested videos are currently being deleted. "
                            "Wait for delete operations to finish, then retry."
                        ),
                    )
                raise HTTPException(status_code=400, detail="No videos available to index.")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Video not found: {exc}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        for item in resolved_filenames:
            safe_name = Path(str(item or "")).name.strip()
            if not safe_name:
                continue
            await self._pipeline_ensure_snapshot(
                case_id=resolved_case_id,
                filename=safe_name,
            )
            await self._pipeline_update_stage(
                case_id=resolved_case_id,
                filename=safe_name,
                stage="base_index",
                status="pending",
                event="background_index_queued",
                details={
                    "frame_interval_seconds": float(frame_interval_seconds),
                    "batch_size": int(batch_size),
                    "force": bool(force),
                },
            )

        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is None:
            raise HTTPException(status_code=500, detail="Background index queue is unavailable.")

        queued_job = await asyncio.to_thread(
            queue_store.enqueue_or_get_active,
            case_id=resolved_case_id,
            filenames=resolved_filenames,
            frame_interval_seconds=frame_interval_seconds,
            batch_size=batch_size,
            force=force,
            job_kind=self.QUEUE_KIND_SEMANTIC_INDEX,
            priority=self.QUEUE_PRIORITY_SEMANTIC_INDEX,
        )
        if not isinstance(queued_job, dict):
            raise HTTPException(status_code=500, detail="Failed to enqueue background indexing job.")

        queue_position = max(0, int(queued_job.get("queue_position", 0)))
        queue_job_id = int(queued_job.get("job_id", 0))
        queue_job_kind = str(queued_job.get("job_kind") or self.QUEUE_KIND_SEMANTIC_INDEX)
        queue_priority = max(1, int(queued_job.get("priority", self.QUEUE_PRIORITY_SEMANTIC_INDEX)))
        created = bool(queued_job.get("created", False))
        reason = str(queued_job.get("reason") or "")
        queued_payload = queued_job.get("payload") if isinstance(queued_job.get("payload"), dict) else {}
        queued_filenames = [
            str(item).strip()
            for item in (queued_payload.get("filenames") or [])
            if str(item).strip()
        ]
        appended_count = max(0, int(queued_job.get("appended_count", 0)))
        appended_filenames = [
            str(item).strip()
            for item in (queued_job.get("appended_filenames") or [])
            if str(item).strip()
        ]

        jobs: dict[str, dict] = self.app.state.index_jobs
        lock: Lock = self.app.state.index_jobs_lock

        def _merge_unique(items: list[str], additions: list[str]) -> list[str]:
            merged: list[str] = []
            seen: set[str] = set()
            for item in items + additions:
                safe = str(item or "").strip()
                if not safe or safe in seen:
                    continue
                seen.add(safe)
                merged.append(safe)
            return merged

        with lock:
            existing = jobs.get(resolved_case_id)
            if isinstance(existing, dict):
                snapshot = self.index_job_snapshot(existing, case_id=resolved_case_id)
            else:
                snapshot = self.index_job_snapshot(None, case_id=resolved_case_id)

        if created:
            with lock:
                queued_state = self.new_index_job_record(
                    case_id=resolved_case_id,
                    filenames=queued_filenames or resolved_filenames,
                    frame_interval_seconds=frame_interval_seconds,
                    batch_size=batch_size,
                    force=force,
                )
                queued_state["running"] = False
                queued_state["status"] = "queued"
                queued_state["queue_job_id"] = queue_job_id
                queued_state["queue_job_kind"] = queue_job_kind
                queued_state["queue_priority"] = queue_priority
                jobs[resolved_case_id] = queued_state
                snapshot = self.index_job_snapshot(queued_state, case_id=resolved_case_id)
            await self._persist_index_snapshot(snapshot)
        elif isinstance(existing, dict):
            with lock:
                live_job = jobs.get(resolved_case_id)
                if isinstance(live_job, dict):
                    existing_files = [
                        str(item).strip()
                        for item in (live_job.get("filenames") or [])
                        if str(item).strip()
                    ]
                    merged_files = _merge_unique(existing_files, queued_filenames)
                    live_job["filenames"] = merged_files
                    live_job["total"] = len(merged_files)
                    live_job["updated_at"] = datetime.now(timezone.utc).isoformat()
                    if queue_job_id > 0:
                        live_job["queue_job_id"] = queue_job_id
                    live_job["queue_job_kind"] = queue_job_kind
                    live_job["queue_priority"] = queue_priority
                    if str(live_job.get("status") or "").strip().lower() in {"", "idle"}:
                        live_job["status"] = str(queued_job.get("status") or "queued")
                        live_job["running"] = str(live_job.get("status") or "").strip().lower() == "running"
                    snapshot = self.index_job_snapshot(live_job, case_id=resolved_case_id)
                else:
                    snapshot = self.index_job_snapshot(existing, case_id=resolved_case_id)
            await self._persist_index_snapshot(snapshot)
        elif snapshot.get("status") == "idle":
            persisted = await self._load_persisted_index_snapshot(resolved_case_id)
            if isinstance(persisted, dict):
                snapshot = self.index_job_snapshot(persisted, case_id=resolved_case_id)
            if snapshot.get("status") == "idle":
                snapshot["status"] = str(queued_job.get("status") or "queued")
                snapshot["running"] = snapshot["status"] == "running"
            if queued_filenames:
                snapshot["filenames"] = queued_filenames
                snapshot["total"] = len(queued_filenames)

        print(
            f"[index-enqueue][{resolved_case_id}] job_id={queue_job_id} "
            f"created={created} reason={reason or 'queued'} "
            f"files={len(resolved_filenames)} queue_position={queue_position} "
            f"frame_interval={frame_interval_seconds} batch_size={batch_size} force={force}"
        )

        return {
            "started": created,
            "case_id": resolved_case_id,
            "job": snapshot,
            "queue": {
                "job_id": queue_job_id,
                "job_kind": queue_job_kind,
                "priority": queue_priority,
                "status": str(queued_job.get("status") or "queued"),
                "position_ahead": queue_position,
                "created": created,
                "reason": reason,
            },
            "message": (
                "Background indexing queued."
                if created
                else (
                    f"Background indexing queue updated with {appended_count} additional video(s)."
                    if reason == "appended_case_active_job" and appended_count > 0
                    else "Background indexing already queued/running for this case."
                )
            ),
            "appended_count": appended_count,
            "appended_filenames": appended_filenames,
            "locked_count": len(locked_filenames),
            "locked_filenames": locked_filenames,
        }

    async def start_background_analysis(
        self,
        *,
        case_id: str | None,
        filenames: list[str] | None,
        frame_interval_seconds: float,
        batch_size: int,
        force: bool,
        analysis_face_people: bool,
        analysis_vehicles: bool,
    ) -> dict:
        locked_filenames: list[str] = []
        if not analysis_face_people and not analysis_vehicles:
            raise HTTPException(
                status_code=400,
                detail="Select at least one analysis type (face_people or vehicles).",
            )

        try:
            resolved_case_id = await asyncio.to_thread(
                self.resolve_case_id_or_default,
                case_id,
            )
            if self._is_case_delete_in_progress(resolved_case_id):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Case {resolved_case_id} is being deleted. "
                        "Wait for deletion to finish, then retry."
                    ),
                )
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, resolved_case_id)
            resolved_filenames = await asyncio.to_thread(
                self.resolve_index_filenames,
                case_paths,
                filenames,
            )
            resolved_filenames, locked_filenames = self._filter_out_deleting_videos(
                case_id=resolved_case_id,
                filenames=resolved_filenames,
            )
            if not resolved_filenames:
                if locked_filenames:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "All requested videos are currently being deleted. "
                            "Wait for delete operations to finish, then retry."
                        ),
                    )
                raise HTTPException(status_code=400, detail="No videos available for analysis.")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Video not found: {exc}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        for item in resolved_filenames:
            safe_name = Path(str(item or "")).name.strip()
            if not safe_name:
                continue
            await self._pipeline_ensure_snapshot(
                case_id=resolved_case_id,
                filename=safe_name,
            )
            await self._pipeline_update_stage(
                case_id=resolved_case_id,
                filename=safe_name,
                stage="analysis",
                status="pending",
                event="background_analysis_queued",
                details={
                    "frame_interval_seconds": float(frame_interval_seconds),
                    "batch_size": int(batch_size),
                    "force": bool(force),
                    "analysis_face_people": bool(analysis_face_people),
                    "analysis_vehicles": bool(analysis_vehicles),
                },
            )

        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is None:
            raise HTTPException(status_code=500, detail="Background analysis queue is unavailable.")

        analysis_metadata: dict[str, Any] = {
            "analysis_face_people": bool(analysis_face_people),
            "analysis_vehicles": bool(analysis_vehicles),
            "analysis_only": True,
        }
        if analysis_face_people:
            analysis_metadata["analysis_face_people_filenames"] = list(resolved_filenames)
        if analysis_vehicles:
            analysis_metadata["analysis_vehicles_filenames"] = list(resolved_filenames)

        queued_job = await asyncio.to_thread(
            queue_store.enqueue_or_get_active,
            case_id=resolved_case_id,
            filenames=resolved_filenames,
            frame_interval_seconds=frame_interval_seconds,
            batch_size=batch_size,
            force=force,
            job_kind=self.QUEUE_KIND_ANALYSIS,
            priority=self.QUEUE_PRIORITY_ANALYSIS,
            metadata=analysis_metadata,
        )
        if not isinstance(queued_job, dict):
            raise HTTPException(status_code=500, detail="Failed to enqueue background analysis job.")

        queue_position = max(0, int(queued_job.get("queue_position", 0)))
        queue_job_id = int(queued_job.get("job_id", 0))
        queue_job_kind = str(queued_job.get("job_kind") or self.QUEUE_KIND_ANALYSIS)
        queue_priority = max(1, int(queued_job.get("priority", self.QUEUE_PRIORITY_ANALYSIS)))
        created = bool(queued_job.get("created", False))
        reason = str(queued_job.get("reason") or "")
        appended_count = max(0, int(queued_job.get("appended_count", 0)))
        appended_filenames = [
            str(item).strip()
            for item in (queued_job.get("appended_filenames") or [])
            if str(item).strip()
        ]
        queued_payload = queued_job.get("payload") if isinstance(queued_job.get("payload"), dict) else {}
        queued_metadata = (
            queued_payload.get("metadata")
            if isinstance(queued_payload.get("metadata"), dict)
            else {}
        )
        effective_face_people = bool(queued_metadata.get("analysis_face_people", analysis_face_people))
        effective_vehicles = bool(queued_metadata.get("analysis_vehicles", analysis_vehicles))

        print(
            f"[analysis-enqueue][{resolved_case_id}] job_id={queue_job_id} "
            f"created={created} reason={reason or 'queued'} "
            f"files={len(resolved_filenames)} queue_position={queue_position} "
            f"face_people={bool(analysis_face_people)} vehicles={bool(analysis_vehicles)} "
            f"frame_interval={frame_interval_seconds} batch_size={batch_size} force={force}"
        )

        return {
            "started": created,
            "case_id": resolved_case_id,
            "filenames": resolved_filenames,
            "queue": {
                "job_id": queue_job_id,
                "job_kind": queue_job_kind,
                "priority": queue_priority,
                "status": str(queued_job.get("status") or "queued"),
                "position_ahead": queue_position,
                "created": created,
                "reason": reason,
            },
            "analysis": {
                "face_people": bool(analysis_face_people),
                "vehicles": bool(analysis_vehicles),
            },
            "effective_analysis": {
                "face_people": effective_face_people,
                "vehicles": effective_vehicles,
            },
            "message": (
                "Background analysis queued."
                if created
                else (
                    f"Background analysis queue updated with {appended_count} additional video(s)."
                    if reason == "appended_case_active_job" and appended_count > 0
                    else (
                        f"Background analysis already queued/running for this case (job #{queue_job_id})."
                        if queue_job_id > 0
                        else "Background analysis already queued/running for this case."
                    )
                )
            ),
            "appended_count": appended_count,
            "appended_filenames": appended_filenames,
            "locked_count": len(locked_filenames),
            "locked_filenames": locked_filenames,
        }

    async def get_background_index_status(self, case_id: str | None) -> dict:
        selected_case_id = ""
        try:
            selected_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            await asyncio.to_thread(self.get_case_paths_or_raise, selected_case_id)
        except ValueError as exc:
            if case_id and str(case_id).strip():
                raise HTTPException(status_code=400, detail=str(exc))
            return self.index_job_snapshot(None, case_id="")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        queue_store = getattr(self.app.state, "index_queue_store", None)
        queue_active = None
        if queue_store is not None:
            try:
                queue_active = await asyncio.to_thread(
                    queue_store.get_case_active,
                    selected_case_id,
                    job_kind=self.QUEUE_KIND_SEMANTIC_INDEX,
                )
            except Exception as exc:
                print(f"[index-queue][{selected_case_id}] status_lookup_failed error={exc}")
                queue_active = None

        jobs: dict[str, dict] = self.app.state.index_jobs
        lock: Lock = self.app.state.index_jobs_lock
        with lock:
            job = jobs.get(selected_case_id)

        if isinstance(job, dict):
            snapshot = self.index_job_snapshot(job, case_id=selected_case_id)
        else:
            persisted = await self._load_persisted_index_snapshot(selected_case_id)
            if isinstance(persisted, dict):
                snapshot = self.index_job_snapshot(persisted, case_id=selected_case_id)
            else:
                snapshot = self.index_job_snapshot(None, case_id=selected_case_id)

        if isinstance(queue_active, dict):
            queue_status = str(queue_active.get("status") or "queued")
            queue_payload = queue_active.get("payload") if isinstance(queue_active.get("payload"), dict) else {}
            queue_filenames = [
                str(item).strip()
                for item in (queue_payload.get("filenames") or [])
                if str(item).strip()
            ]
            if queue_filenames:
                if not snapshot.get("filenames"):
                    snapshot["filenames"] = queue_filenames
                else:
                    existing_files = [
                        str(item).strip()
                        for item in (snapshot.get("filenames") or [])
                        if str(item).strip()
                    ]
                    merged_files: list[str] = []
                    seen: set[str] = set()
                    for item in existing_files + queue_filenames:
                        safe = str(item or "").strip()
                        if not safe or safe in seen:
                            continue
                        seen.add(safe)
                        merged_files.append(safe)
                    snapshot["filenames"] = merged_files
                snapshot["total"] = max(int(snapshot.get("total", 0)), len(snapshot.get("filenames") or []))
            if snapshot.get("status") == "idle" and queue_status in {"queued", "running"}:
                snapshot["status"] = queue_status
                snapshot["running"] = queue_status == "running"
            snapshot["queue"] = {
                "job_id": int(queue_active.get("job_id", 0)),
                "job_kind": str(queue_active.get("job_kind") or self.QUEUE_KIND_SEMANTIC_INDEX),
                "priority": max(1, int(queue_active.get("priority", self.QUEUE_PRIORITY_SEMANTIC_INDEX))),
                "status": queue_status,
                "position_ahead": max(0, int(queue_active.get("queue_position", 0))),
                "attempt_count": int(queue_active.get("attempt_count", 0)),
                "enqueued_at": str(queue_active.get("enqueued_at") or ""),
                "started_at": str(queue_active.get("started_at") or ""),
            }

        snapshots = await self._pipeline_list_case_snapshots(case_id=selected_case_id)
        snapshots_by_filename: dict[str, dict] = {}
        for item in snapshots:
            if not isinstance(item, dict):
                continue
            key = str(item.get("filename") or "").strip()
            if not key:
                continue
            snapshots_by_filename[key] = item

        file_progress = self._build_file_progress_rows(
            filenames=self._unique_filenames(snapshot.get("filenames") or []),
            snapshots_by_filename=snapshots_by_filename,
            stage_name="base_index",
            fallback_status=str(snapshot.get("status") or "pending"),
            current_filename=str(snapshot.get("current_filename") or ""),
            current_processed_frames=int(snapshot.get("current_video_processed_frames", 0) or 0),
            current_total_frames=int(snapshot.get("current_video_total_frames", 0) or 0),
            current_progress_percent=float(snapshot.get("current_video_progress_percent", 0.0) or 0.0),
        )
        snapshot["file_progress"] = file_progress

        return snapshot

    async def get_background_analysis_status(
        self,
        case_id: str | None,
        category: str | None = None,
    ) -> dict:
        selected_category = self._normalize_analysis_status_category(category)
        selected_case_id = ""
        try:
            selected_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            await asyncio.to_thread(self.get_case_paths_or_raise, selected_case_id)
        except ValueError as exc:
            if case_id and str(case_id).strip():
                raise HTTPException(status_code=400, detail=str(exc))
            return self._default_analysis_status_payload(case_id="")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        payload = self._default_analysis_status_payload(case_id=selected_case_id)

        queue_store = getattr(self.app.state, "index_queue_store", None)
        latest_job = None
        if queue_store is not None:
            try:
                if hasattr(queue_store, "get_case_latest"):
                    latest_job = await asyncio.to_thread(
                        queue_store.get_case_latest,
                        selected_case_id,
                        job_kind=self.QUEUE_KIND_ANALYSIS,
                    )
                else:
                    latest_job = await asyncio.to_thread(
                        queue_store.get_case_active,
                        selected_case_id,
                        job_kind=self.QUEUE_KIND_ANALYSIS,
                    )
            except Exception as exc:
                print(f"[analysis-queue][{selected_case_id}] status_lookup_failed error={exc}")
                latest_job = None

        if not isinstance(latest_job, dict):
            return payload

        queue_status = str(latest_job.get("status") or "").strip().lower()
        queue_payload = latest_job.get("payload") if isinstance(latest_job.get("payload"), dict) else {}
        all_filenames = self._unique_filenames(queue_payload.get("filenames") or [])
        metadata = queue_payload.get("metadata") if isinstance(queue_payload.get("metadata"), dict) else {}
        analysis_face_people = bool(metadata.get("analysis_face_people", False))
        analysis_vehicles = bool(metadata.get("analysis_vehicles", False))
        face_people_filenames = self._unique_filenames(
            metadata.get("analysis_face_people_filenames") or [],
        )
        vehicle_filenames = self._unique_filenames(
            metadata.get("analysis_vehicles_filenames") or [],
        )

        filenames = list(all_filenames)
        if selected_category == self.ANALYSIS_STATUS_CATEGORY_FACE_PEOPLE:
            if face_people_filenames:
                filenames = face_people_filenames
            elif (
                analysis_face_people
                and (
                    not analysis_vehicles
                    or (not face_people_filenames and not vehicle_filenames)
                )
            ):
                # Backward compatibility: old jobs may not have per-category filename metadata.
                filenames = list(all_filenames)
            else:
                filenames = []
            analysis_vehicles = False
        elif selected_category == self.ANALYSIS_STATUS_CATEGORY_VEHICLES:
            if vehicle_filenames:
                filenames = vehicle_filenames
            elif (
                analysis_vehicles
                and (
                    not analysis_face_people
                    or (not face_people_filenames and not vehicle_filenames)
                )
            ):
                # Backward compatibility: old jobs may not have per-category filename metadata.
                filenames = list(all_filenames)
            else:
                filenames = []
            analysis_face_people = False

        if selected_category and not filenames:
            payload["analysis"] = {
                "face_people": bool(analysis_face_people),
                "vehicles": bool(analysis_vehicles),
            }
            payload["analysis_face_people_filenames"] = self._unique_filenames(face_people_filenames)
            payload["analysis_vehicles_filenames"] = self._unique_filenames(vehicle_filenames)
            payload["message"] = (
                "No Face & People analysis job found for this case."
                if selected_category == self.ANALYSIS_STATUS_CATEGORY_FACE_PEOPLE
                else "No Vehicles analysis job found for this case."
            )
            return payload

        queue_error = str(latest_job.get("error") or "").strip()

        snapshots = await self._pipeline_list_case_snapshots(case_id=selected_case_id)
        snapshots_by_filename: dict[str, dict] = {}
        for item in snapshots:
            if not isinstance(item, dict):
                continue
            key = str(item.get("filename") or "").strip()
            if not key:
                continue
            snapshots_by_filename[key] = item

        if queue_status == "interrupted" and selected_category:
            recoverable_filenames = self._recoverable_analysis_filenames(
                filenames=filenames,
                snapshots_by_filename=snapshots_by_filename,
                category=selected_category,
            )
            filenames = recoverable_filenames
            if not recoverable_filenames:
                queue_status = "idle"
                queue_error = ""

        progress = self._analysis_progress_from_snapshots(
            filenames=filenames,
            snapshots_by_filename=snapshots_by_filename,
        )
        final_status = self._analysis_status_from_queue(
            queue_status,
            failed_count=int(progress.get("failed", 0)),
        )

        try:
            queue_priority = max(1, int(latest_job.get("priority", self.QUEUE_PRIORITY_ANALYSIS)))
        except (TypeError, ValueError):
            queue_priority = int(self.QUEUE_PRIORITY_ANALYSIS)

        queue_position = max(0, int(latest_job.get("queue_position", 0))) if queue_status == "queued" else 0
        progress_completed = max(0, int(progress.get("completed", 0)))
        progress_total = max(0, int(progress.get("total", 0)))
        progress_percent = float(progress.get("percent", 0.0))

        payload["status"] = final_status
        payload["queue"] = {
            "job_id": int(latest_job.get("job_id", 0)),
            "job_kind": str(latest_job.get("job_kind") or self.QUEUE_KIND_ANALYSIS),
            "priority": queue_priority,
            "status": queue_status or "idle",
            "position_ahead": queue_position,
            "attempt_count": int(latest_job.get("attempt_count", 0)),
            "enqueued_at": str(latest_job.get("enqueued_at") or ""),
            "started_at": str(latest_job.get("started_at") or ""),
            "finished_at": str(latest_job.get("finished_at") or ""),
        }
        payload["progress"] = {
            "completed": progress_completed,
            "total": progress_total,
            "percent": progress_percent,
        }
        payload["filenames"] = filenames
        payload["file_progress"] = self._build_file_progress_rows(
            filenames=filenames,
            snapshots_by_filename=snapshots_by_filename,
            stage_name="analysis",
            fallback_status=queue_status or "pending",
        )
        payload["analysis_face_people_filenames"] = self._unique_filenames(face_people_filenames)
        payload["analysis_vehicles_filenames"] = self._unique_filenames(vehicle_filenames)
        payload["analysis"] = {
            "face_people": analysis_face_people,
            "vehicles": analysis_vehicles,
        }
        payload["message"] = self._analysis_status_message(
            status=final_status,
            queue_error=queue_error,
            completed=progress_completed,
            total=progress_total,
        )
        return payload

    async def cancel_interrupted_analysis(
        self,
        *,
        case_id: str | None,
        category: str,
        filenames: list[str],
    ) -> dict:
        selected_category = self._normalize_analysis_status_category(category)
        if not selected_category:
            raise HTTPException(
                status_code=400,
                detail="category is required (face_people or vehicles).",
            )

        try:
            selected_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, selected_case_id)
            resolved_filenames = await asyncio.to_thread(
                self.resolve_index_filenames,
                case_paths,
                filenames,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Video not found: {exc}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        snapshots = await self._pipeline_list_case_snapshots(case_id=selected_case_id)
        snapshots_by_filename: dict[str, dict] = {}
        for item in snapshots:
            if not isinstance(item, dict):
                continue
            key = str(item.get("filename") or "").strip()
            if not key:
                continue
            snapshots_by_filename[key] = item

        cancellable_statuses = {"interrupted", "pending", "queued"}

        cancelled: list[str] = []
        not_interrupted: list[str] = []
        skipped: list[str] = []

        for filename in resolved_filenames:
            snapshot = snapshots_by_filename.get(filename)
            if not isinstance(snapshot, dict):
                skipped.append(filename)
                continue

            stage_status = self._stage_status(snapshot, "analysis")
            if stage_status in {"completed", "failed", "skipped"}:
                not_interrupted.append(filename)
                continue
            if stage_status not in cancellable_statuses:
                not_interrupted.append(filename)
                continue
            if not self._analysis_stage_matches_category(
                snapshot=snapshot,
                category=selected_category,
            ):
                skipped.append(filename)
                continue

            await self._pipeline_update_stage(
                case_id=selected_case_id,
                filename=filename,
                stage="analysis",
                status="skipped",
                event="analysis_interrupted_cancelled_by_user",
                details={
                    "cancelled_from_interrupted": True,
                    "cancelled_category": selected_category,
                    "source": "user_cancel_interrupted",
                    "previous_stage_status": stage_status,
                },
            )
            cancelled.append(filename)

        refreshed_status = await self.get_background_analysis_status(
            selected_case_id,
            selected_category,
        )
        remaining_filenames = self._unique_filenames(refreshed_status.get("filenames") or [])

        return {
            "case_id": selected_case_id,
            "category": selected_category,
            "requested_filenames": resolved_filenames,
            "cancelled_filenames": cancelled,
            "not_interrupted_filenames": not_interrupted,
            "skipped_filenames": skipped,
            "cancelled_count": len(cancelled),
            "remaining_interrupted_filenames": remaining_filenames,
            "remaining_interrupted_count": len(remaining_filenames),
            "status": refreshed_status,
            "message": (
                f"Cancelled {len(cancelled)} {selected_category} file(s). "
                f"Remaining interrupted: {len(remaining_filenames)}. "
                f"Already resolved: {len(not_interrupted)}. "
                f"Category-mismatched: {len(skipped)}."
            ),
        }

    async def get_pipeline_status(self, case_id: str | None, filename: str | None) -> dict:
        selected_case_id = ""
        try:
            selected_case_id = await asyncio.to_thread(self.resolve_case_id_or_default, case_id)
            case_paths = await asyncio.to_thread(self.get_case_paths_or_raise, selected_case_id)
        except ValueError as exc:
            if case_id and str(case_id).strip():
                raise HTTPException(status_code=400, detail=str(exc))
            return {"case_id": "", "count": 0, "pipelines": []}
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        snapshots = await self._pipeline_list_case_snapshots(case_id=selected_case_id)
        by_filename = {}
        for item in snapshots:
            if not isinstance(item, dict):
                continue
            key = str(item.get("filename") or "").strip()
            if not key:
                continue
            by_filename[key] = item

        if filename and str(filename).strip():
            safe_filename = Path(str(filename or "")).name.strip()
            if not safe_filename:
                raise HTTPException(status_code=400, detail="filename is required")
            target = by_filename.get(safe_filename)
            if target is None:
                video_path = case_paths.videos_dir / safe_filename
                if not video_path.exists() or not video_path.is_file():
                    raise HTTPException(status_code=404, detail=f"Video not found: {filename}")
                target = await self._pipeline_ensure_snapshot(
                    case_id=selected_case_id,
                    filename=safe_filename,
                )
            if target is None:
                target = self._default_pipeline(selected_case_id, safe_filename)
            return {
                "case_id": selected_case_id,
                "filename": safe_filename,
                "pipeline": target,
            }

        payload: list[dict] = []
        for file_path in sorted(case_paths.videos_dir.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.video_extensions:
                continue
            item = by_filename.get(file_path.name)
            if item is None:
                item = await self._pipeline_ensure_snapshot(
                    case_id=selected_case_id,
                    filename=file_path.name,
                )
            if item is None:
                item = self._default_pipeline(selected_case_id, file_path.name)
            payload.append(item)

        return {
            "case_id": selected_case_id,
            "count": len(payload),
            "pipelines": payload,
        }
