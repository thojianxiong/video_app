from __future__ import annotations

import asyncio
import os
import signal
from threading import Lock
from typing import Any


class ProcessControlService:
    ALLOWED_QUEUE_JOB_KINDS = {
        "semantic_index",
        "analysis",
        "analysis_face_people",
        "analysis_face_identity",
        "analysis_vehicles",
        "triage_timeline",
    }

    def __init__(
        self,
        *,
        app: Any,
        utc_now_iso: Any,
        index_job_snapshot: Any,
    ) -> None:
        self.app = app
        self.utc_now_iso = utc_now_iso
        self.index_job_snapshot = index_job_snapshot

    @staticmethod
    def _normalize_case_id(value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("case_id is required")
        return normalized

    @staticmethod
    def _normalize_job_ids(job_ids: list[int] | tuple[int, ...] | set[int]) -> list[int]:
        unique: list[int] = []
        seen: set[int] = set()
        for raw in job_ids:
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                continue
            if parsed <= 0 or parsed in seen:
                continue
            seen.add(parsed)
            unique.append(parsed)
        if not unique:
            raise ValueError("job_ids is required")
        return unique

    @staticmethod
    def _normalize_single_job_id(job_id: Any) -> int:
        try:
            parsed = int(job_id)
        except (TypeError, ValueError):
            parsed = 0
        if parsed <= 0:
            raise ValueError("job_id must be greater than 0")
        return parsed

    def _get_queue_store(self) -> Any:
        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is None:
            raise ValueError("Queue store is unavailable.")
        return queue_store

    def _get_case_scoped_queue_job(
        self,
        *,
        case_id: str,
        job_id: int,
    ) -> dict[str, Any]:
        queue_store = self._get_queue_store()
        if not hasattr(queue_store, "get_job"):
            raise ValueError("Queue store does not support job lookup.")
        job = queue_store.get_job(int(job_id))
        if not isinstance(job, dict):
            raise ValueError("Queue job not found.")

        job_case_id = str(job.get("case_id") or "").strip()
        if job_case_id != case_id:
            raise ValueError("Queue job does not belong to the selected case.")

        job_kind = str(job.get("job_kind") or "").strip().lower()
        if job_kind not in self.ALLOWED_QUEUE_JOB_KINDS:
            raise ValueError(f"Queue job kind '{job_kind}' is not supported for this action.")
        return job

    @staticmethod
    def _is_active_job(job: dict) -> bool:
        status = str(job.get("status") or "")
        return bool(job.get("running")) or status in {"queued", "running", "cancelling"}

    @staticmethod
    def _normalize_filenames(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        output: list[str] = []
        seen: set[str] = set()
        for raw in value:
            safe = str(raw or "").strip()
            if not safe or safe in seen:
                continue
            seen.add(safe)
            output.append(safe)
        return output

    @staticmethod
    def _safe_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)

    @staticmethod
    def _safe_float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    @staticmethod
    def _normalize_stage_status(value: Any, fallback: str = "pending") -> str:
        normalized = str(value or "").strip().lower()
        if normalized:
            return normalized
        return str(fallback or "pending").strip().lower() or "pending"

    @staticmethod
    def _stage_name_for_job_kind(job_kind: str) -> str:
        normalized = str(job_kind or "").strip().lower()
        if normalized == "semantic_index":
            return "base_index"
        if normalized == "analysis_face_people":
            return "analysis_face_people"
        if normalized == "analysis_face_identity":
            return "analysis_face_identity"
        if normalized == "analysis_vehicles":
            return "analysis_vehicles"
        if normalized == "analysis":
            return "analysis"
        if normalized == "triage_timeline":
            return "triage"
        return ""

    def _load_case_pipeline_snapshots_map(
        self,
        *,
        case_id: str,
        cache: dict[str, dict[str, dict]],
    ) -> dict[str, dict]:
        safe_case_id = str(case_id or "").strip()
        if not safe_case_id:
            return {}
        cached = cache.get(safe_case_id)
        if isinstance(cached, dict):
            return cached

        store = getattr(self.app.state, "video_pipeline_store", None)
        mapping: dict[str, dict] = {}
        if store is None or not hasattr(store, "list_case_snapshots"):
            cache[safe_case_id] = mapping
            return mapping

        try:
            snapshots = store.list_case_snapshots(safe_case_id)
        except Exception:
            snapshots = []
        for item in snapshots:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename") or "").strip()
            if not filename:
                continue
            mapping[filename] = item
        cache[safe_case_id] = mapping
        return mapping

    def _build_file_progress_rows(
        self,
        *,
        case_id: str,
        filenames: list[str],
        stage_name: str,
        fallback_status: str,
        snapshot_cache: dict[str, dict[str, dict]],
        current_filename: str = "",
        current_processed_frames: int = 0,
        current_total_frames: int = 0,
        current_progress_percent: float = 0.0,
        expected_job_kind: str = "",
        expected_submission_id: str = "",
    ) -> list[dict]:
        safe_filenames = self._normalize_filenames(filenames)
        if not safe_filenames:
            return []

        stage = str(stage_name or "").strip()
        default_status = self._normalize_stage_status(fallback_status, fallback="pending")
        safe_current_filename = str(current_filename or "").strip()
        safe_current_processed = max(0, self._safe_int(current_processed_frames))
        safe_current_total = max(0, self._safe_int(current_total_frames))
        safe_current_percent = min(100.0, max(0.0, self._safe_float(current_progress_percent)))
        safe_expected_job_kind = str(expected_job_kind or "").strip().lower()
        safe_expected_submission_id = str(expected_submission_id or "").strip()
        snapshots_by_filename = self._load_case_pipeline_snapshots_map(
            case_id=case_id,
            cache=snapshot_cache,
        )

        rows: list[dict] = []
        for filename in safe_filenames:
            snapshot = snapshots_by_filename.get(filename)
            stage_payload = None
            if (
                isinstance(snapshot, dict)
                and isinstance(snapshot.get("stages"), dict)
                and stage
                and isinstance(snapshot["stages"].get(stage), dict)
            ):
                stage_payload = snapshot["stages"][stage]

            status = self._normalize_stage_status(
                stage_payload.get("status") if isinstance(stage_payload, dict) else "",
                fallback=default_status,
            )
            details = (
                stage_payload.get("details")
                if isinstance(stage_payload, dict) and isinstance(stage_payload.get("details"), dict)
                else {}
            )
            details_job_kind = str(
                details.get("analysis_job_kind")
                or details.get("queue_job_kind")
                or details.get("job_kind")
                or ""
            ).strip().lower()
            if not details_job_kind:
                source = str(details.get("source") or "").strip().lower()
                if source == "background_index":
                    details_job_kind = "semantic_index"
            details_submission_id = str(details.get("submission_id") or "").strip()

            kind_matches = (
                (not safe_expected_job_kind)
                or (
                    bool(details_job_kind)
                    and details_job_kind == safe_expected_job_kind
                )
            )
            submission_matches = (
                (not safe_expected_submission_id)
                or (
                    bool(details_submission_id)
                    and details_submission_id == safe_expected_submission_id
                )
            )
            if not kind_matches or not submission_matches:
                status = "pending"
                details = {}

            processed = max(0, self._safe_int(details.get("processed_frames", 0)))
            total = max(
                0,
                self._safe_int(
                    details.get("estimated_total_frames", details.get("total_frames", 0)),
                ),
            )
            if total > 0 and total < processed:
                total = processed

            percent = self._safe_float(details.get("progress_percent"), fallback=0.0)
            if total > 0:
                percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
            else:
                percent = min(100.0, max(0.0, percent))

            is_current = bool(safe_current_filename) and filename == safe_current_filename
            if is_current:
                if safe_current_processed > processed:
                    processed = safe_current_processed
                if safe_current_total > total:
                    total = safe_current_total
                if total > 0 and total < processed:
                    total = processed
                if total > 0:
                    percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
                else:
                    percent = max(percent, safe_current_percent)

            if status in {"completed", "skipped", "failed", "interrupted"}:
                percent = 100.0
            elif status == "running":
                if total > 0:
                    percent = min(100.0, max(0.0, (float(processed) / float(total)) * 100.0))
                elif is_current and safe_current_percent > 0:
                    percent = min(100.0, max(0.0, safe_current_percent))
                # Keep running rows below 100% so users can distinguish "still working" from done.
                if percent >= 100.0:
                    percent = 99.0
            elif status in {"queued", "pending", "starting"}:
                processed = 0
                total = 0
                percent = 0.0

            rows.append(
                {
                    "filename": filename,
                    "status": status,
                    "processed_frames": int(processed),
                    "estimated_total_frames": int(total),
                    "progress_percent": float(min(100.0, max(0.0, percent))),
                    "is_current": bool(is_current),
                }
            )
            if status not in {"queued", "pending", "starting"}:
                if isinstance(details.get("phase"), str) and str(details.get("phase")).strip():
                    rows[-1]["phase"] = str(details.get("phase")).strip()
                if isinstance(details.get("phase_label"), str) and str(details.get("phase_label")).strip():
                    rows[-1]["phase_label"] = str(details.get("phase_label")).strip()
        return rows

    def list_active_processes_sync(self, case_id: str | None = None) -> dict:
        selected_case_id = str(case_id or "").strip()
        jobs: dict[str, dict] = self.app.state.index_jobs
        lock: Lock = self.app.state.index_jobs_lock
        processes_all: list[dict] = []
        completed_processes_all: list[dict] = []
        pipeline_snapshot_cache: dict[str, dict[str, dict]] = {}
        pending_row_statuses = {"queued", "pending", "starting"}
        running_row_statuses = {"running", "cancelling"}
        terminal_row_statuses = {
            "completed",
            "processed",
            "success",
            "succeeded",
            "skipped",
            "failed",
            "error",
            "cancelled",
            "canceled",
            "interrupted",
            "aborted",
            "completed_with_errors",
        }

        def _normalize_status_token(value: Any) -> str:
            return str(value or "").strip().lower().replace(" ", "_")

        def _terminal_status_from_job_status(value: Any) -> str:
            normalized = _normalize_status_token(value)
            if normalized in terminal_row_statuses:
                return normalized
            if normalized in running_row_statuses:
                return "interrupted"
            if normalized in pending_row_statuses:
                return "completed"
            return "completed"

        def _is_terminal_row_status(value: Any) -> bool:
            normalized = _normalize_status_token(value)
            return normalized in terminal_row_statuses

        def _completed_fallback_filenames(
            *,
            item: dict[str, Any] | None,
            metadata: dict[str, Any] | None,
            filenames: list[str] | None,
        ) -> list[str]:
            candidates: list[str] = []
            seen: set[str] = set()

            def _push(value: Any) -> None:
                safe = str(value or "").strip()
                if not safe or safe in seen:
                    return
                seen.add(safe)
                candidates.append(safe)

            safe_metadata = metadata if isinstance(metadata, dict) else {}
            safe_item = item if isinstance(item, dict) else {}
            for key in (
                "processed_filename",
                "current_filename",
                "head_filename",
                "target_filename",
            ):
                _push(safe_item.get(key))
                _push(safe_metadata.get(key))

            safe_filenames = self._normalize_filenames(filenames)
            if not candidates and safe_filenames:
                # Queue worker runs one file per queue job; first filename is the processed head.
                _push(safe_filenames[0])
            return candidates

        def _canonicalize_terminal_row(
            row: dict[str, Any],
            *,
            fallback_status: str,
            fallback_filename: str = "",
        ) -> dict[str, Any]:
            normalized_row = dict(row)
            safe_filename = str(
                normalized_row.get("filename")
                or fallback_filename
                or ""
            ).strip()
            if safe_filename:
                normalized_row["filename"] = safe_filename
            normalized_row["status"] = _terminal_status_from_job_status(
                normalized_row.get("status") or fallback_status
            )
            normalized_row["progress_percent"] = 100.0
            normalized_row["is_current"] = False
            processed = max(0, self._safe_int(normalized_row.get("processed_frames", 0)))
            total = max(
                processed,
                self._safe_int(
                    normalized_row.get("estimated_total_frames", normalized_row.get("total_frames", 0)),
                ),
            )
            normalized_row["processed_frames"] = int(processed)
            normalized_row["estimated_total_frames"] = int(total)
            if not str(normalized_row.get("phase") or "").strip():
                normalized_row.pop("phase", None)
            if not str(normalized_row.get("phase_label") or "").strip():
                normalized_row.pop("phase_label", None)
            return normalized_row

        def _build_terminal_rows_for_completed_item(
            *,
            file_progress: list[dict[str, Any]] | Any,
            filenames: list[str],
            fallback_status: str,
            fallback_filenames: list[str] | None = None,
        ) -> list[dict[str, Any]]:
            safe_filenames = self._normalize_filenames(filenames)
            safe_fallback_filenames = self._normalize_filenames(fallback_filenames)
            terminal_rows: list[dict[str, Any]] = []
            seen: set[str] = set()
            raw_rows = file_progress if isinstance(file_progress, list) else []
            for raw_row in raw_rows:
                if not isinstance(raw_row, dict):
                    continue
                if not _is_terminal_row_status(raw_row.get("status")):
                    continue
                normalized_row = _canonicalize_terminal_row(raw_row, fallback_status=fallback_status)
                filename = str(normalized_row.get("filename") or "").strip()
                if not filename or filename in seen:
                    continue
                if safe_filenames and filename not in safe_filenames:
                    continue
                seen.add(filename)
                terminal_rows.append(normalized_row)

            if terminal_rows:
                return terminal_rows

            fallback_targets = safe_fallback_filenames or safe_filenames[:1]
            for filename in fallback_targets:
                if filename in seen:
                    continue
                seen.add(filename)
                terminal_rows.append(
                    _canonicalize_terminal_row(
                        {"filename": filename},
                        fallback_status=fallback_status,
                    )
                )
            return terminal_rows

        with lock:
            for raw_case_id, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                case_id = str(raw_case_id or "").strip()
                if not case_id:
                    continue
                status = str(job.get("status") or "")
                if not self._is_active_job(job):
                    continue
                snapshot = self.index_job_snapshot(job, case_id=case_id)
                snapshot_filenames = [
                    str(name).strip()
                    for name in (snapshot.get("filenames") or [])
                    if str(name).strip()
                ]
                current_filename = str(snapshot.get("current_filename") or "")
                current_video_processed_frames = max(
                    0,
                    self._safe_int(snapshot.get("current_video_processed_frames", 0)),
                )
                current_video_total_frames = max(
                    0,
                    self._safe_int(snapshot.get("current_video_total_frames", 0)),
                )
                current_video_progress_percent = min(
                    100.0,
                    max(0.0, self._safe_float(snapshot.get("current_video_progress_percent", 0.0))),
                )
                file_progress = self._build_file_progress_rows(
                    case_id=case_id,
                    filenames=snapshot_filenames,
                    stage_name="base_index",
                    fallback_status=str(snapshot.get("status", status)),
                    snapshot_cache=pipeline_snapshot_cache,
                    current_filename=current_filename,
                    current_processed_frames=current_video_processed_frames,
                    current_total_frames=current_video_total_frames,
                    current_progress_percent=current_video_progress_percent,
                )
                processes_all.append(
                    {
                        "type": "background_index",
                        "case_id": case_id,
                        "status": snapshot.get("status", status),
                        "current_filename": current_filename,
                        "completed": int(snapshot.get("completed", 0)),
                        "total": int(snapshot.get("total", 0)),
                        "progress_percent": float(snapshot.get("progress_percent", 0.0)),
                        "current_video_processed_frames": current_video_processed_frames,
                        "current_video_total_frames": current_video_total_frames,
                        "current_video_progress_percent": current_video_progress_percent,
                        "started_at": snapshot.get("started_at", ""),
                        "updated_at": snapshot.get("updated_at", ""),
                        "filenames_count": len(snapshot_filenames),
                        "filenames_preview": snapshot_filenames[:5],
                        "filenames": snapshot_filenames,
                        "file_progress": file_progress,
                    }
                )

        queue_store = getattr(self.app.state, "index_queue_store", None)
        def _serialize_queue_job(item: dict[str, Any], *, process_type: str) -> dict[str, Any]:
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            filenames = [
                str(name).strip()
                for name in (payload.get("filenames") or [])
                if str(name).strip()
            ]
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            face_people_filenames = [
                str(name).strip()
                for name in (metadata.get("analysis_face_people_filenames") or [])
                if str(name).strip()
            ]
            vehicles_filenames = [
                str(name).strip()
                for name in (metadata.get("analysis_vehicles_filenames") or [])
                if str(name).strip()
            ]
            face_identity_filenames = [
                str(name).strip()
                for name in (metadata.get("analysis_face_identity_filenames") or [])
                if str(name).strip()
            ]
            submission_id = str(metadata.get("submission_id") or "").strip()
            submission_created_at = str(metadata.get("submission_created_at") or "").strip()
            submission_kind = str(metadata.get("submission_kind") or "").strip().lower()
            queue_case_id = str(item.get("case_id") or "")
            status = str(item.get("status") or "")
            job_kind = str(item.get("job_kind") or "")
            completed_fallback_filenames = _completed_fallback_filenames(
                item=item,
                metadata=metadata,
                filenames=filenames,
            )
            file_progress = self._build_file_progress_rows(
                case_id=queue_case_id,
                filenames=filenames,
                stage_name=self._stage_name_for_job_kind(job_kind),
                fallback_status="pending" if process_type == "queue_job_completed" else status,
                snapshot_cache=pipeline_snapshot_cache,
                expected_job_kind=job_kind,
                expected_submission_id=submission_id,
            )
            if process_type == "queue_job_completed":
                file_progress = _build_terminal_rows_for_completed_item(
                    file_progress=file_progress,
                    filenames=filenames,
                    fallback_status=status,
                    fallback_filenames=completed_fallback_filenames,
                )
                filenames = [
                    str(row.get("filename") or "").strip()
                    for row in file_progress
                    if isinstance(row, dict) and str(row.get("filename") or "").strip()
                ]
            return {
                "type": process_type,
                "queue_job_id": int(item.get("job_id", 0)),
                "queue_job_ids": [int(item.get("job_id", 0))] if int(item.get("job_id", 0)) > 0 else [],
                "job_kind": job_kind,
                "priority": int(item.get("priority", 0)),
                "case_id": queue_case_id,
                "status": status,
                "queue_position": max(0, int(item.get("queue_position", 0))),
                "attempt_count": int(item.get("attempt_count", 0)),
                "filenames_count": len(filenames),
                "filenames_preview": filenames[:5],
                "filenames": filenames,
                "file_progress": file_progress,
                "submission_id": submission_id,
                "submission_created_at": submission_created_at,
                "submission_kind": submission_kind,
                "metadata": {
                    "analysis_face_people": bool(metadata.get("analysis_face_people", False)),
                    "analysis_vehicles": bool(metadata.get("analysis_vehicles", False)),
                    "analysis_face_identity": bool(metadata.get("analysis_face_identity", False)),
                    "analysis_only": bool(metadata.get("analysis_only", False)),
                    "analysis_mode": str(metadata.get("analysis_mode") or ""),
                    "analysis_face_people_filenames": face_people_filenames,
                    "analysis_vehicles_filenames": vehicles_filenames,
                    "analysis_face_identity_filenames": face_identity_filenames,
                    "submission_id": submission_id,
                    "submission_created_at": submission_created_at,
                    "submission_kind": submission_kind,
                },
                "enqueued_at": str(item.get("enqueued_at") or ""),
                "started_at": str(item.get("started_at") or ""),
                "finished_at": str(item.get("finished_at") or ""),
                "updated_at": str(item.get("updated_at") or ""),
            }

        def _collapse_queue_items_by_submission(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            def _merge_unique(left: list[str], right: list[str]) -> list[str]:
                merged: list[str] = []
                seen: set[str] = set()
                for value in [*left, *right]:
                    safe = str(value or "").strip()
                    if not safe or safe in seen:
                        continue
                    seen.add(safe)
                    merged.append(safe)
                return merged

            def _pick_earliest(left: str, right: str) -> str:
                safe_left = str(left or "").strip()
                safe_right = str(right or "").strip()
                if not safe_left:
                    return safe_right
                if not safe_right:
                    return safe_left
                return safe_left if safe_left <= safe_right else safe_right

            def _pick_latest(left: str, right: str) -> str:
                safe_left = str(left or "").strip()
                safe_right = str(right or "").strip()
                if not safe_left:
                    return safe_right
                if not safe_right:
                    return safe_left
                return safe_left if safe_left >= safe_right else safe_right

            def _merge_status(current: str, incoming: str, *, process_type: str) -> str:
                current_norm = str(current or "").strip().lower()
                incoming_norm = str(incoming or "").strip().lower()
                if process_type == "queue_job":
                    running_statuses = {"running", "cancelling"}
                    queued_statuses = {"queued", "pending", "starting"}
                    if current_norm in running_statuses or incoming_norm in running_statuses:
                        return "running"
                    if current_norm in queued_statuses or incoming_norm in queued_statuses:
                        return "queued"
                error_statuses = {
                    "completed_with_errors",
                    "failed",
                    "error",
                    "cancelled",
                    "canceled",
                    "interrupted",
                    "aborted",
                }
                success_statuses = {"completed", "processed", "success", "succeeded", "skipped"}
                if current_norm in error_statuses or incoming_norm in error_statuses:
                    return "completed_with_errors"
                if current_norm in success_statuses and incoming_norm in success_statuses:
                    return "completed"
                return incoming_norm or current_norm

            def _merge_file_progress(
                existing_rows: list[dict[str, Any]],
                incoming_rows: list[dict[str, Any]],
                *,
                filenames_order: list[str],
                process_type: str,
            ) -> list[dict[str, Any]]:
                def _normalize_row_status(value: Any) -> str:
                    return _normalize_status_token(value)

                def _canonicalize_pending_row(row: dict[str, Any]) -> dict[str, Any]:
                    normalized_row = dict(row)
                    normalized_row["status"] = "pending"
                    normalized_row["processed_frames"] = 0
                    normalized_row["estimated_total_frames"] = 0
                    normalized_row["progress_percent"] = 0.0
                    normalized_row["is_current"] = False
                    normalized_row.pop("phase", None)
                    normalized_row.pop("phase_label", None)
                    return normalized_row

                def _canonicalize_progress_row(
                    row: dict[str, Any],
                    *,
                    row_process_type: str,
                ) -> dict[str, Any]:
                    normalized_row = dict(row)
                    status_value = _normalize_row_status(normalized_row.get("status"))
                    if row_process_type == "queue_job" and status_value in pending_row_statuses:
                        normalized_row = _canonicalize_pending_row(normalized_row)
                    return normalized_row

                def _row_priority(row: dict[str, Any], *, row_process_type: str) -> int:
                    status_value = _normalize_row_status(row.get("status"))
                    if row_process_type == "queue_job":
                        if status_value in running_row_statuses:
                            return 3
                        if status_value in pending_row_statuses:
                            return 2
                        if status_value in terminal_row_statuses:
                            return 1
                        return 0
                    if row_process_type == "queue_job_completed":
                        if status_value in terminal_row_statuses:
                            return 3
                        if status_value in running_row_statuses:
                            return 2
                        if status_value in pending_row_statuses:
                            return 1
                        return 0
                    return 0

                rows_by_filename: dict[str, dict[str, Any]] = {}
                for row in [*existing_rows, *incoming_rows]:
                    if not isinstance(row, dict):
                        continue
                    normalized_row = _canonicalize_progress_row(row, row_process_type=process_type)
                    if (
                        process_type == "queue_job_completed"
                        and not _is_terminal_row_status(normalized_row.get("status"))
                    ):
                        continue
                    filename = str(normalized_row.get("filename") or "").strip()
                    if not filename:
                        continue
                    current = rows_by_filename.get(filename)
                    if not isinstance(current, dict):
                        rows_by_filename[filename] = dict(normalized_row)
                        continue
                    current_priority = _row_priority(current, row_process_type=process_type)
                    incoming_priority = _row_priority(normalized_row, row_process_type=process_type)
                    if incoming_priority > current_priority:
                        rows_by_filename[filename] = dict(normalized_row)
                        continue
                    if incoming_priority < current_priority:
                        continue
                    if process_type == "queue_job" and incoming_priority <= 2:
                        # For active queue cards, avoid replacing clean pending/terminal rows with stale
                        # historical values on equal-priority ties.
                        continue
                    current_percent = self._safe_float(current.get("progress_percent", 0.0), fallback=0.0)
                    incoming_percent = self._safe_float(
                        normalized_row.get("progress_percent", 0.0),
                        fallback=0.0,
                    )
                    if incoming_percent >= current_percent:
                        rows_by_filename[filename] = dict(normalized_row)
                ordered_rows: list[dict[str, Any]] = []
                for filename in filenames_order:
                    row = rows_by_filename.pop(filename, None)
                    if isinstance(row, dict):
                        ordered_rows.append(row)
                for row in rows_by_filename.values():
                    ordered_rows.append(row)
                if process_type == "queue_job":
                    ordered_rows = [
                        _canonicalize_progress_row(row, row_process_type=process_type)
                        for row in ordered_rows
                        if isinstance(row, dict)
                    ]
                return ordered_rows

            def _sanitize_active_queue_rows(item: dict[str, Any]) -> None:
                if str(item.get("type") or "").strip().lower() != "queue_job":
                    return
                item_status = _normalize_status_token(item.get("status"))
                raw_rows = item.get("file_progress")
                if not isinstance(raw_rows, list):
                    item["file_progress"] = []
                    return
                sanitized_rows: list[dict[str, Any]] = []
                for raw_row in raw_rows:
                    if not isinstance(raw_row, dict):
                        continue
                    row = dict(raw_row)
                    row_status = _normalize_status_token(row.get("status"))
                    should_force_pending = False
                    if item_status in pending_row_statuses:
                        # Queued/pending cards should always render as clean queued state.
                        should_force_pending = row_status not in running_row_statuses
                    elif row_status in pending_row_statuses:
                        should_force_pending = True
                    if should_force_pending:
                        row["status"] = "pending"
                        row["processed_frames"] = 0
                        row["estimated_total_frames"] = 0
                        row["progress_percent"] = 0.0
                        row["is_current"] = False
                        row.pop("phase", None)
                        row.pop("phase_label", None)
                    sanitized_rows.append(row)
                item["file_progress"] = sanitized_rows

            grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
            ordered_refs: list[tuple[str, Any]] = []

            for raw_item in items:
                if not isinstance(raw_item, dict):
                    continue
                process_type = str(raw_item.get("type") or "").strip().lower()
                metadata = raw_item.get("metadata") if isinstance(raw_item.get("metadata"), dict) else {}
                submission_id = str(
                    raw_item.get("submission_id")
                    or metadata.get("submission_id")
                    or "",
                ).strip()
                if process_type not in {"queue_job", "queue_job_completed"} or not submission_id:
                    ordered_refs.append(("item", raw_item))
                    continue

                case_id_value = str(raw_item.get("case_id") or "").strip()
                job_kind_value = str(raw_item.get("job_kind") or "").strip().lower()
                group_key = (case_id_value, job_kind_value, submission_id)
                if group_key not in grouped:
                    clone = dict(raw_item)
                    clone_metadata = dict(metadata)
                    clone["metadata"] = clone_metadata
                    clone["submission_id"] = submission_id
                    clone["submission_created_at"] = str(
                        raw_item.get("submission_created_at")
                        or clone_metadata.get("submission_created_at")
                        or "",
                    ).strip()
                    clone["submission_kind"] = str(
                        raw_item.get("submission_kind")
                        or clone_metadata.get("submission_kind")
                        or job_kind_value,
                    ).strip().lower()
                    clone["queue_job_ids"] = sorted(
                        {
                            int(value)
                            for value in [
                                raw_item.get("queue_job_id"),
                                *(
                                    raw_item.get("queue_job_ids")
                                    if isinstance(raw_item.get("queue_job_ids"), list)
                                    else []
                                ),
                            ]
                            if self._safe_int(value, 0) > 0
                        }
                    )
                    if process_type == "queue_job":
                        clone_progress = (
                            clone.get("file_progress")
                            if isinstance(clone.get("file_progress"), list)
                            else []
                        )
                        clone["file_progress"] = _merge_file_progress(
                            [],
                            [row for row in clone_progress if isinstance(row, dict)],
                            filenames_order=self._normalize_filenames(clone.get("filenames")),
                            process_type=process_type,
                        )
                    grouped[group_key] = clone
                    ordered_refs.append(("group", group_key))
                    continue

                aggregate = grouped[group_key]
                aggregate_metadata = (
                    aggregate.get("metadata")
                    if isinstance(aggregate.get("metadata"), dict)
                    else {}
                )

                merged_filenames = _merge_unique(
                    self._normalize_filenames(aggregate.get("filenames")),
                    self._normalize_filenames(raw_item.get("filenames")),
                )
                aggregate["filenames"] = merged_filenames
                aggregate["filenames_count"] = len(merged_filenames)
                aggregate["filenames_preview"] = merged_filenames[:5]

                aggregate["queue_job_id"] = max(
                    self._safe_int(aggregate.get("queue_job_id", 0)),
                    self._safe_int(raw_item.get("queue_job_id", 0)),
                )
                aggregate["queue_job_ids"] = sorted(
                    {
                        int(value)
                        for value in [
                            aggregate.get("queue_job_id"),
                            raw_item.get("queue_job_id"),
                            *(
                                aggregate.get("queue_job_ids")
                                if isinstance(aggregate.get("queue_job_ids"), list)
                                else []
                            ),
                            *(
                                raw_item.get("queue_job_ids")
                                if isinstance(raw_item.get("queue_job_ids"), list)
                                else []
                            ),
                        ]
                        if self._safe_int(value, 0) > 0
                    }
                )
                aggregate["priority"] = min(
                    max(0, self._safe_int(aggregate.get("priority", 0))),
                    max(0, self._safe_int(raw_item.get("priority", 0))),
                )
                aggregate["queue_position"] = min(
                    max(0, self._safe_int(aggregate.get("queue_position", 0))),
                    max(0, self._safe_int(raw_item.get("queue_position", 0))),
                )
                aggregate["attempt_count"] = (
                    max(0, self._safe_int(aggregate.get("attempt_count", 0)))
                    + max(0, self._safe_int(raw_item.get("attempt_count", 0)))
                )
                aggregate["status"] = _merge_status(
                    str(aggregate.get("status") or ""),
                    str(raw_item.get("status") or ""),
                    process_type=process_type,
                )
                aggregate["enqueued_at"] = _pick_earliest(
                    str(aggregate.get("enqueued_at") or ""),
                    str(raw_item.get("enqueued_at") or ""),
                )
                aggregate["started_at"] = _pick_earliest(
                    str(aggregate.get("started_at") or ""),
                    str(raw_item.get("started_at") or ""),
                )
                aggregate["finished_at"] = _pick_latest(
                    str(aggregate.get("finished_at") or ""),
                    str(raw_item.get("finished_at") or ""),
                )
                aggregate["updated_at"] = _pick_latest(
                    str(aggregate.get("updated_at") or ""),
                    str(raw_item.get("updated_at") or ""),
                )

                incoming_metadata = (
                    raw_item.get("metadata")
                    if isinstance(raw_item.get("metadata"), dict)
                    else {}
                )
                aggregate_metadata["analysis_face_people"] = bool(
                    aggregate_metadata.get("analysis_face_people", False)
                ) or bool(incoming_metadata.get("analysis_face_people", False))
                aggregate_metadata["analysis_vehicles"] = bool(
                    aggregate_metadata.get("analysis_vehicles", False)
                ) or bool(incoming_metadata.get("analysis_vehicles", False))
                aggregate_metadata["analysis_face_identity"] = bool(
                    aggregate_metadata.get("analysis_face_identity", False)
                ) or bool(incoming_metadata.get("analysis_face_identity", False))
                aggregate_metadata["analysis_only"] = bool(
                    aggregate_metadata.get("analysis_only", False)
                ) or bool(incoming_metadata.get("analysis_only", False))
                if not str(aggregate_metadata.get("analysis_mode") or "").strip():
                    aggregate_metadata["analysis_mode"] = str(incoming_metadata.get("analysis_mode") or "")

                for key in (
                    "analysis_face_people_filenames",
                    "analysis_vehicles_filenames",
                    "analysis_face_identity_filenames",
                ):
                    aggregate_metadata[key] = _merge_unique(
                        self._normalize_filenames(aggregate_metadata.get(key)),
                        self._normalize_filenames(incoming_metadata.get(key)),
                    )

                if not str(aggregate.get("submission_created_at") or "").strip():
                    aggregate["submission_created_at"] = str(
                        raw_item.get("submission_created_at")
                        or incoming_metadata.get("submission_created_at")
                        or "",
                    ).strip()
                if not str(aggregate.get("submission_kind") or "").strip():
                    aggregate["submission_kind"] = str(
                        raw_item.get("submission_kind")
                        or incoming_metadata.get("submission_kind")
                        or aggregate.get("job_kind")
                        or "",
                    ).strip().lower()
                aggregate_metadata["submission_id"] = submission_id
                aggregate_metadata["submission_created_at"] = str(
                    aggregate.get("submission_created_at") or ""
                ).strip()
                aggregate_metadata["submission_kind"] = str(
                    aggregate.get("submission_kind") or ""
                ).strip().lower()
                aggregate["metadata"] = aggregate_metadata

                existing_progress = (
                    aggregate.get("file_progress")
                    if isinstance(aggregate.get("file_progress"), list)
                    else []
                )
                incoming_progress = (
                    raw_item.get("file_progress")
                    if isinstance(raw_item.get("file_progress"), list)
                    else []
                )
                aggregate["file_progress"] = _merge_file_progress(
                    [row for row in existing_progress if isinstance(row, dict)],
                    [row for row in incoming_progress if isinstance(row, dict)],
                    filenames_order=merged_filenames,
                    process_type=process_type,
                )

            collapsed: list[dict[str, Any]] = []
            for ref_kind, ref_value in ordered_refs:
                if ref_kind == "item":
                    if isinstance(ref_value, dict):
                        collapsed.append(ref_value)
                    continue
                if ref_kind != "group":
                    continue
                grouped_item = grouped.get(ref_value)
                if isinstance(grouped_item, dict):
                    collapsed.append(grouped_item)
            for item in collapsed:
                item_type = str(item.get("type") or "").strip().lower()
                if item_type == "queue_job":
                    item_progress = (
                        item.get("file_progress")
                        if isinstance(item.get("file_progress"), list)
                        else []
                    )
                    item["file_progress"] = _merge_file_progress(
                        [],
                        [row for row in item_progress if isinstance(row, dict)],
                        filenames_order=self._normalize_filenames(item.get("filenames")),
                        process_type="queue_job",
                    )
                    _sanitize_active_queue_rows(item)
                    continue
                if item_type != "queue_job_completed":
                    continue
                terminal_rows = _build_terminal_rows_for_completed_item(
                    file_progress=item.get("file_progress"),
                    filenames=self._normalize_filenames(item.get("filenames")),
                    fallback_status=str(item.get("status") or ""),
                    fallback_filenames=_completed_fallback_filenames(
                        item=item,
                        metadata=(
                            item.get("metadata")
                            if isinstance(item.get("metadata"), dict)
                            else {}
                        ),
                        filenames=self._normalize_filenames(item.get("filenames")),
                    ),
                )
                item["file_progress"] = terminal_rows
                terminal_filenames = [
                    str(row.get("filename") or "").strip()
                    for row in terminal_rows
                    if isinstance(row, dict) and str(row.get("filename") or "").strip()
                ]
                item["filenames"] = terminal_filenames
                item["filenames_count"] = len(terminal_filenames)
                item["filenames_preview"] = terminal_filenames[:5]
            return collapsed

        if queue_store is not None and hasattr(queue_store, "list_active_jobs"):
            try:
                active_queue_jobs = queue_store.list_active_jobs(limit=500)
            except Exception:
                active_queue_jobs = []
            for item in active_queue_jobs:
                if not isinstance(item, dict):
                    continue
                processes_all.append(_serialize_queue_job(item, process_type="queue_job"))

            if hasattr(queue_store, "list_recent_jobs"):
                try:
                    recent_queue_jobs = queue_store.list_recent_jobs(limit=500)
                except Exception:
                    recent_queue_jobs = []
                for item in recent_queue_jobs:
                    if not isinstance(item, dict):
                        continue
                    completed_processes_all.append(
                        _serialize_queue_job(item, process_type="queue_job_completed")
                    )

        if selected_case_id:
            processes = [
                item
                for item in processes_all
                if str(item.get("case_id") or "").strip() == selected_case_id
            ]
            completed_processes = [
                item
                for item in completed_processes_all
                if str(item.get("case_id") or "").strip() == selected_case_id
            ]
        else:
            processes = list(processes_all)
            completed_processes = list(completed_processes_all)
        processes = _collapse_queue_items_by_submission(processes)
        completed_processes = _collapse_queue_items_by_submission(completed_processes)

        blocked_by_other_case = False
        blocking_case_id = ""
        blocking_message = ""
        if selected_case_id:
            current_case_has_waiting = any(
                str(item.get("case_id") or "").strip() == selected_case_id
                and str(item.get("status") or "").strip().lower() == "queued"
                for item in processes_all
            )
            running_other_case_item = next(
                (
                    item
                    for item in processes_all
                    if str(item.get("case_id") or "").strip() != selected_case_id
                    and str(item.get("status") or "").strip().lower() == "running"
                    and str(item.get("type") or "").strip().lower() in {"queue_job", "background_index"}
                ),
                None,
            )
            if current_case_has_waiting and isinstance(running_other_case_item, dict):
                blocked_by_other_case = True
                blocking_case_id = str(running_other_case_item.get("case_id") or "").strip()
                blocking_kind = str(running_other_case_item.get("job_kind") or "").strip().lower()
                if str(running_other_case_item.get("type") or "").strip().lower() == "background_index":
                    blocking_kind = "semantic_index"
                blocking_label = {
                    "semantic_index": "Semantic Index",
                    "analysis_face_people": "Face & People Analysis",
                    "analysis_face_identity": "Face Identity Top-up",
                    "analysis_vehicles": "Vehicle Analysis",
                    "analysis": "Analysis",
                    "triage_timeline": "Triage Timeline",
                }.get(blocking_kind, "background task")
                blocking_message = (
                    f"Another case ({blocking_case_id}) is currently running {blocking_label}. "
                    "Current case queued jobs will start after that running task finishes."
                )

        return {
            "shutdown_requested": bool(getattr(self.app.state, "shutdown_requested", False)),
            "shutdown_requested_at": str(getattr(self.app.state, "shutdown_requested_at", "") or ""),
            "queue_scope_case_id": selected_case_id,
            "blocked_by_other_case": bool(blocked_by_other_case),
            "blocking_case_id": blocking_case_id,
            "blocking_message": blocking_message,
            "count": len(processes),
            "processes": processes,
            "completed_count": len(completed_processes),
            "completed_processes": completed_processes,
        }

    def cancel_running_index_jobs_sync(self) -> dict:
        jobs: dict[str, dict] = self.app.state.index_jobs
        tasks: dict[str, asyncio.Task] = self.app.state.index_tasks
        lock: Lock = self.app.state.index_jobs_lock
        cancelled_case_ids: set[str] = set()
        now = self.utc_now_iso()

        with lock:
            for raw_case_id, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                case_id = str(raw_case_id or "").strip()
                if not case_id:
                    continue
                if not self._is_active_job(job):
                    continue
                job["cancel_requested"] = True
                job["status"] = "cancelling"
                job["running"] = False
                job["updated_at"] = now
                cancelled_case_ids.add(case_id)

            for raw_case_id, task in list(tasks.items()):
                case_id = str(raw_case_id or "").strip()
                if not case_id or not isinstance(task, asyncio.Task):
                    continue
                if task.done():
                    continue
                task.cancel()
                cancelled_case_ids.add(case_id)
                job = jobs.get(case_id)
                if isinstance(job, dict):
                    job["cancel_requested"] = True
                    job["status"] = "cancelling"
                    job["running"] = False
                    job["updated_at"] = now

        return {
            "cancelled_count": len(cancelled_case_ids),
            "cancelled_case_ids": sorted(cancelled_case_ids),
        }

    def cancel_case_index_jobs_sync(
        self,
        *,
        case_id: str,
        force: bool = False,
        reason: str = "Cancelled by user request.",
    ) -> dict:
        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            raise ValueError("case_id is required")

        jobs: dict[str, dict] = self.app.state.index_jobs
        tasks: dict[str, asyncio.Task] = self.app.state.index_tasks
        lock: Lock = self.app.state.index_jobs_lock
        now = self.utc_now_iso()

        requested = False
        task_cancelled = False

        with lock:
            job = jobs.get(normalized_case_id)
            if isinstance(job, dict) and self._is_active_job(job):
                job["cancel_requested"] = True
                job["status"] = "cancelling"
                job["running"] = False
                job["updated_at"] = now
                requested = True

            task = tasks.get(normalized_case_id)
            if force and isinstance(task, asyncio.Task) and not task.done():
                task.cancel()
                task_cancelled = True
                requested = True
                if isinstance(job, dict):
                    job["cancel_requested"] = True
                    job["status"] = "cancelling"
                    job["running"] = False
                    job["updated_at"] = now

        queue_cancelled = 0
        queue_store = getattr(self.app.state, "index_queue_store", None)
        if queue_store is not None:
            try:
                queue_cancelled = int(
                    queue_store.cancel_case_active(
                        normalized_case_id,
                        reason=str(reason or "").strip() or "Cancelled by user request.",
                        job_kind="semantic_index",
                    )
                )
                if queue_cancelled > 0:
                    requested = True
            except Exception as exc:
                print(f"[index-queue][{normalized_case_id}] cancel_case_active_failed error={exc}")

        active_after_cancel = False
        with lock:
            remaining = jobs.get(normalized_case_id)
            if isinstance(remaining, dict):
                active_after_cancel = self._is_active_job(remaining)

        return {
            "case_id": normalized_case_id,
            "cancel_requested": bool(requested),
            "task_cancelled": bool(task_cancelled),
            "queue_cancelled_count": max(0, int(queue_cancelled)),
            "active_after_cancel": bool(active_after_cancel),
            "message": (
                "Cancellation requested."
                if requested
                else "No active semantic indexing process found for this case."
            ),
        }

    def schedule_process_exit(self, delay_seconds: float = 1.0) -> None:
        loop = asyncio.get_running_loop()

        def _trigger_exit() -> None:
            try:
                signal.raise_signal(signal.SIGINT)
            except Exception:
                os._exit(0)

        loop.call_later(max(0.2, float(delay_seconds)), _trigger_exit)

    async def list_processes(self, *, case_id: str | None = None) -> dict:
        return await asyncio.to_thread(self.list_active_processes_sync, case_id)

    async def cancel_case_index_jobs(
        self,
        *,
        case_id: str,
        force: bool = False,
        reason: str = "Cancelled by user request.",
    ) -> dict:
        return await asyncio.to_thread(
            self.cancel_case_index_jobs_sync,
            case_id=case_id,
            force=force,
            reason=reason,
        )

    def delete_queue_jobs_sync(
        self,
        *,
        case_id: str,
        job_ids: list[int],
        cancel_running: bool = False,
    ) -> dict:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_job_ids = self._normalize_job_ids(job_ids)
        queue_store = self._get_queue_store()
        if not hasattr(queue_store, "delete_jobs"):
            raise ValueError("Queue store is unavailable.")

        not_found_ids: list[int] = []
        wrong_case_ids: list[int] = []
        unsupported_kind_ids: list[int] = []
        eligible_ids: list[int] = []

        for job_id in normalized_job_ids:
            job = queue_store.get_job(int(job_id)) if hasattr(queue_store, "get_job") else None
            if not isinstance(job, dict):
                not_found_ids.append(int(job_id))
                continue
            job_case_id = str(job.get("case_id") or "").strip()
            if job_case_id != normalized_case_id:
                wrong_case_ids.append(int(job_id))
                continue
            job_kind = str(job.get("job_kind") or "").strip().lower()
            if job_kind not in self.ALLOWED_QUEUE_JOB_KINDS:
                unsupported_kind_ids.append(int(job_id))
                continue
            eligible_ids.append(int(job_id))

        result: dict[str, Any] = {}
        if eligible_ids:
            result = queue_store.delete_jobs(
                job_ids=eligible_ids,
                cancel_running=bool(cancel_running),
                reason="Removed from queue by user request.",
            )
            if not isinstance(result, dict):
                result = {}

        removed_count = int(result.get("removed_count", 0))
        cancelled_running_count = int(result.get("cancelled_running_count", 0))
        skipped_running_count = int(result.get("skipped_running_count", 0))
        effective_not_found = [
            *[int(item) for item in (result.get("not_found_ids") or [])],
            *not_found_ids,
        ]

        return {
            "case_id": normalized_case_id,
            "requested_count": len(normalized_job_ids),
            "eligible_count": len(eligible_ids),
            "found_count": int(result.get("found_count", 0)),
            "removed_count": removed_count,
            "cancelled_running_count": cancelled_running_count,
            "skipped_running_count": skipped_running_count,
            "removed_job_ids": result.get("removed_job_ids") or [],
            "cancelled_running_job_ids": result.get("cancelled_running_job_ids") or [],
            "skipped_running_job_ids": result.get("skipped_running_job_ids") or [],
            "not_found_ids": sorted(set(effective_not_found)),
            "wrong_case_job_ids": sorted(set(wrong_case_ids)),
            "unsupported_kind_job_ids": sorted(set(unsupported_kind_ids)),
            "affected_case_ids": [
                str(item).strip()
                for item in (result.get("affected_case_ids") or [])
                if str(item).strip()
            ],
            "message": "Queue items removed from queue tracking.",
        }

    def stop_queue_jobs_sync(
        self,
        *,
        case_id: str,
        job_ids: list[int],
    ) -> dict:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_job_ids = self._normalize_job_ids(job_ids)
        queue_store = self._get_queue_store()
        if not hasattr(queue_store, "cancel_jobs"):
            raise ValueError("Queue store does not support stopping jobs.")

        not_found_ids: list[int] = []
        wrong_case_ids: list[int] = []
        unsupported_kind_ids: list[int] = []
        terminal_ids: list[int] = []
        eligible_ids: list[int] = []
        semantic_running_cases: set[str] = set()

        for job_id in normalized_job_ids:
            job = queue_store.get_job(int(job_id)) if hasattr(queue_store, "get_job") else None
            if not isinstance(job, dict):
                not_found_ids.append(int(job_id))
                continue
            job_case_id = str(job.get("case_id") or "").strip()
            if job_case_id != normalized_case_id:
                wrong_case_ids.append(int(job_id))
                continue
            job_kind = str(job.get("job_kind") or "").strip().lower()
            if job_kind not in self.ALLOWED_QUEUE_JOB_KINDS:
                unsupported_kind_ids.append(int(job_id))
                continue
            status = str(job.get("status") or "").strip().lower()
            if status not in {"queued", "running"}:
                terminal_ids.append(int(job_id))
                continue
            if status == "running" and job_kind == "semantic_index":
                semantic_running_cases.add(job_case_id)
            eligible_ids.append(int(job_id))

        result: dict[str, Any] = {}
        if eligible_ids:
            result = queue_store.cancel_jobs(
                job_ids=eligible_ids,
                include_running=True,
                reason="Stop requested by user. Will stop after current step.",
            )
            if not isinstance(result, dict):
                result = {}

        semantic_cancel_count = 0
        if semantic_running_cases:
            jobs: dict[str, dict] = self.app.state.index_jobs
            lock: Lock = self.app.state.index_jobs_lock
            now = self.utc_now_iso()
            with lock:
                for semantic_case_id in sorted(semantic_running_cases):
                    snapshot = jobs.get(semantic_case_id)
                    if not isinstance(snapshot, dict):
                        continue
                    snapshot["cancel_requested"] = True
                    snapshot["status"] = "cancelling"
                    snapshot["running"] = False
                    snapshot["updated_at"] = now
                    semantic_cancel_count += 1

        return {
            "case_id": normalized_case_id,
            "requested_count": len(normalized_job_ids),
            "eligible_count": len(eligible_ids),
            "cancelled_count": int(result.get("cancelled_count", 0)),
            "cancelled_job_ids": result.get("cancelled_job_ids") or [],
            "skipped_running_count": int(result.get("skipped_running_count", 0)),
            "skipped_running_job_ids": result.get("skipped_running_job_ids") or [],
            "terminal_count": int(result.get("terminal_count", 0)) + len(terminal_ids),
            "terminal_job_ids": sorted(
                {
                    *[int(item) for item in (result.get("terminal_job_ids") or [])],
                    *terminal_ids,
                }
            ),
            "not_found_ids": sorted(
                {
                    *[int(item) for item in (result.get("not_found_ids") or [])],
                    *not_found_ids,
                }
            ),
            "wrong_case_job_ids": sorted(set(wrong_case_ids)),
            "unsupported_kind_job_ids": sorted(set(unsupported_kind_ids)),
            "semantic_cancelled_count": int(semantic_cancel_count),
            "affected_case_ids": sorted(
                {
                    *[
                        str(item).strip()
                        for item in (result.get("affected_case_ids") or [])
                        if str(item).strip()
                    ],
                    *semantic_running_cases,
                }
            ),
            "message": "Stop requested. Running tasks will stop after the current in-flight step.",
        }

    def run_queue_job_sync(
        self,
        *,
        case_id: str,
        job_id: int,
        filenames: list[str],
    ) -> dict:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_job_id = self._normalize_single_job_id(job_id)
        selected_filenames = self._normalize_filenames(filenames)
        queue_store = self._get_queue_store()
        if not hasattr(queue_store, "prioritize_job"):
            raise ValueError("Queue store does not support run-now priority.")

        current_job = self._get_case_scoped_queue_job(
            case_id=normalized_case_id,
            job_id=normalized_job_id,
        )
        current_status = str(current_job.get("status") or "").strip().lower()
        if current_status == "running":
            return {
                "case_id": normalized_case_id,
                "job_id": normalized_job_id,
                "status": "running",
                "updated": False,
                "queue": current_job,
                "message": "Job is already running.",
            }
        if current_status != "queued":
            raise ValueError("Only queued jobs can be run immediately.")

        result = queue_store.prioritize_job(
            job_id=normalized_job_id,
            priority=1,
            filenames_front=selected_filenames,
        )
        if not isinstance(result, dict):
            raise ValueError("Queue store returned an invalid response.")
        if not bool(result.get("found", False)):
            raise ValueError("Queue job not found.")
        if str(result.get("blocked_status") or "").strip().lower() == "running":
            return {
                "case_id": normalized_case_id,
                "job_id": normalized_job_id,
                "status": "running",
                "updated": False,
                "queue": result.get("job") if isinstance(result.get("job"), dict) else {},
                "message": "Job is already running.",
            }

        updated_job = result.get("job") if isinstance(result.get("job"), dict) else {}
        queue_payload = {}
        if isinstance(updated_job, dict):
            queue_payload = {
                "job_id": int(updated_job.get("job_id", normalized_job_id)),
                "job_kind": str(updated_job.get("job_kind") or ""),
                "priority": int(updated_job.get("priority", 0)),
                "status": str(updated_job.get("status") or ""),
                "position_ahead": int(updated_job.get("queue_position", 0)),
                "attempt_count": int(updated_job.get("attempt_count", 0)),
                "enqueued_at": str(updated_job.get("enqueued_at") or ""),
                "started_at": str(updated_job.get("started_at") or ""),
                "updated_at": str(updated_job.get("updated_at") or ""),
            }

        return {
            "case_id": normalized_case_id,
            "job_id": normalized_job_id,
            "updated": bool(result.get("updated", False)),
            "front_applied_count": int(result.get("front_applied_count", 0)),
            "front_applied_filenames": result.get("front_applied_filenames") or [],
            "front_missing_filenames": result.get("front_missing_filenames") or [],
            "queue": queue_payload,
            "message": str(result.get("message") or "Queue item moved to front."),
        }

    def remove_queue_job_files_sync(
        self,
        *,
        case_id: str,
        job_id: int,
        filenames: list[str],
        allow_running: bool = False,
    ) -> dict:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_job_id = self._normalize_single_job_id(job_id)
        self._get_case_scoped_queue_job(
            case_id=normalized_case_id,
            job_id=normalized_job_id,
        )
        queue_store = self._get_queue_store()
        if not hasattr(queue_store, "remove_files_from_job"):
            raise ValueError("Queue store is unavailable.")

        result = queue_store.remove_files_from_job(
            job_id=int(normalized_job_id),
            filenames=filenames,
            allow_running=bool(allow_running),
            reason="Selected files removed from queue by user request.",
        )
        if not isinstance(result, dict):
            raise ValueError("Queue store returned an invalid response.")

        found = bool(result.get("found", False))
        if not found:
            raise ValueError("Queue job not found.")
        if bool(result.get("blocked_running", False)):
            raise ValueError("Queue job is running. Stop it first, then remove files.")

        case_id = str(result.get("case_id") or "").strip()
        job_kind = str(result.get("job_kind") or "").strip().lower()
        deleted_job = bool(result.get("deleted_job", False))
        remaining_filenames = self._normalize_filenames(result.get("remaining_filenames"))
        updated_queue_job = (
            result.get("job")
            if isinstance(result.get("job"), dict)
            else {}
        )

        if case_id and job_kind == "semantic_index":
            jobs: dict[str, dict] = self.app.state.index_jobs
            lock: Lock = self.app.state.index_jobs_lock
            now = self.utc_now_iso()
            with lock:
                job = jobs.get(case_id)
                if isinstance(job, dict) and not bool(job.get("running")):
                    if deleted_job or not remaining_filenames:
                        job["status"] = "idle"
                        job["running"] = False
                        job["cancel_requested"] = False
                        job["queue_job_id"] = 0
                        job["queue_job_kind"] = ""
                        job["queue_priority"] = 0
                        job["filenames"] = []
                        job["total"] = 0
                        job["updated_at"] = now
                    else:
                        job["status"] = "queued"
                        job["running"] = False
                        job["cancel_requested"] = False
                        job["queue_job_id"] = int(updated_queue_job.get("job_id", job_id))
                        job["queue_job_kind"] = str(
                            updated_queue_job.get("job_kind")
                            or job_kind
                            or "semantic_index"
                        )
                        job["queue_priority"] = int(
                            updated_queue_job.get("priority", job.get("queue_priority", 50))
                        )
                        job["filenames"] = list(remaining_filenames)
                        job["total"] = len(remaining_filenames)
                        job["updated_at"] = now

        queue_payload = {}
        if isinstance(updated_queue_job, dict):
            queue_payload = {
                "job_id": int(updated_queue_job.get("job_id", 0)),
                "job_kind": str(updated_queue_job.get("job_kind") or ""),
                "priority": int(updated_queue_job.get("priority", 0)),
                "status": str(updated_queue_job.get("status") or ""),
                "position_ahead": int(updated_queue_job.get("queue_position", 0)),
                "attempt_count": int(updated_queue_job.get("attempt_count", 0)),
                "enqueued_at": str(updated_queue_job.get("enqueued_at") or ""),
                "started_at": str(updated_queue_job.get("started_at") or ""),
                "updated_at": str(updated_queue_job.get("updated_at") or ""),
            }

        return {
            "job_id": int(result.get("job_id", normalized_job_id)),
            "case_id": case_id,
            "job_kind": job_kind,
            "deleted_job": deleted_job,
            "requested_count": int(result.get("requested_count", 0)),
            "removed_count": int(result.get("removed_count", 0)),
            "remaining_count": int(result.get("remaining_count", 0)),
            "removed_filenames": result.get("removed_filenames") or [],
            "remaining_filenames": remaining_filenames,
            "not_found_filenames": result.get("not_found_filenames") or [],
            "queue": queue_payload,
            "message": str(result.get("message") or "Queue item updated."),
        }

    async def delete_queue_jobs(
        self,
        *,
        case_id: str,
        job_ids: list[int],
        cancel_running: bool = False,
    ) -> dict:
        return await asyncio.to_thread(
            self.delete_queue_jobs_sync,
            case_id=case_id,
            job_ids=job_ids,
            cancel_running=cancel_running,
        )

    async def stop_queue_jobs(
        self,
        *,
        case_id: str,
        job_ids: list[int],
    ) -> dict:
        return await asyncio.to_thread(
            self.stop_queue_jobs_sync,
            case_id=case_id,
            job_ids=job_ids,
        )

    async def run_queue_job(
        self,
        *,
        case_id: str,
        job_id: int,
        filenames: list[str],
    ) -> dict:
        return await asyncio.to_thread(
            self.run_queue_job_sync,
            case_id=case_id,
            job_id=job_id,
            filenames=filenames,
        )

    async def remove_queue_job_files(
        self,
        *,
        case_id: str,
        job_id: int,
        filenames: list[str],
        allow_running: bool = False,
    ) -> dict:
        return await asyncio.to_thread(
            self.remove_queue_job_files_sync,
            case_id=case_id,
            job_id=job_id,
            filenames=filenames,
            allow_running=allow_running,
        )

    async def graceful_shutdown(self, *, confirm: bool) -> dict:
        if not confirm:
            raise ValueError("confirm=true is required for shutdown.")

        process_snapshot = await asyncio.to_thread(self.list_active_processes_sync)
        cancel_payload = await asyncio.to_thread(self.cancel_running_index_jobs_sync)
        self.app.state.shutdown_requested = True
        self.app.state.shutdown_requested_at = self.utc_now_iso()
        self.schedule_process_exit(1.0)

        return {
            "accepted": True,
            "message": "Graceful shutdown scheduled.",
            "active_process_count": int(process_snapshot.get("count", 0)),
            "active_processes": process_snapshot.get("processes", []),
            "cancelled_count": int(cancel_payload.get("cancelled_count", 0)),
            "cancelled_case_ids": cancel_payload.get("cancelled_case_ids", []),
            "shutdown_requested_at": str(self.app.state.shutdown_requested_at),
        }
