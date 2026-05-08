from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class IndexQueueStore:
    DEFAULT_JOB_KIND = "semantic_index"
    DEFAULT_PRIORITY = 50

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._lock = Lock()
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path), timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _managed_connection(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_db(self) -> None:
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS index_job_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    job_kind TEXT NOT NULL DEFAULT 'semantic_index',
                    priority INTEGER NOT NULL DEFAULT 50,
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
            existing_columns = {
                str(row["name"]).strip().lower()
                for row in conn.execute("PRAGMA table_info(index_job_queue)").fetchall()
            }
            column_defaults = {
                "job_kind": "TEXT NOT NULL DEFAULT 'semantic_index'",
                "priority": "INTEGER NOT NULL DEFAULT 50",
                "error": "TEXT NOT NULL DEFAULT ''",
                "started_at": "TEXT NOT NULL DEFAULT ''",
                "finished_at": "TEXT NOT NULL DEFAULT ''",
                "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            }
            for column_name, column_sql in column_defaults.items():
                if column_name in existing_columns:
                    continue
                conn.execute(
                    f"""
                    ALTER TABLE index_job_queue
                    ADD COLUMN {column_name} {column_sql}
                    """
                )
                existing_columns.add(column_name)

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_job_queue_status_id
                ON index_job_queue(status, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_job_queue_status_priority_id
                ON index_job_queue(status, priority, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_job_queue_case_status
                ON index_job_queue(case_id, status, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_job_queue_case_kind_status
                ON index_job_queue(case_id, job_kind, status, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_index_job_queue_dedupe_status
                ON index_job_queue(dedupe_key, status, id)
                """
            )
            conn.commit()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_case_id(case_id: str) -> str:
        normalized = str(case_id or "").strip()
        if not normalized:
            raise ValueError("case_id is required")
        return normalized

    @classmethod
    def _normalize_job_kind(cls, job_kind: str) -> str:
        normalized = str(job_kind or "").strip().lower()
        if not normalized:
            return cls.DEFAULT_JOB_KIND
        return normalized

    @classmethod
    def _normalize_job_kinds(
        cls,
        job_kinds: list[str] | tuple[str, ...] | set[str] | None,
    ) -> list[str]:
        if not job_kinds:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in job_kinds:
            kind = cls._normalize_job_kind(str(item or ""))
            if not kind or kind in seen:
                continue
            seen.add(kind)
            normalized.append(kind)
        return normalized

    @classmethod
    def _normalize_priority(cls, priority: int) -> int:
        try:
            value = int(priority)
        except Exception:
            value = cls.DEFAULT_PRIORITY
        return max(1, min(100, value))

    @staticmethod
    def _normalize_filenames(filenames: list[str] | tuple[str, ...]) -> list[str]:
        output: list[str] = []
        for item in filenames:
            name = str(item or "").strip()
            if not name:
                continue
            output.append(name)
        if not output:
            raise ValueError("filenames is required")
        return output

    @staticmethod
    def _merge_unique_filenames(existing: list[str], incoming: list[str]) -> tuple[list[str], list[str]]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in existing:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            merged.append(name)

        appended: list[str] = []
        for item in incoming:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            merged.append(name)
            appended.append(name)

        return merged, appended

    @classmethod
    def _build_payload(
        cls,
        *,
        case_id: str,
        filenames: list[str],
        frame_interval_seconds: float,
        batch_size: int,
        force: bool,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_metadata = metadata if isinstance(metadata, dict) else {}
        return {
            "case_id": cls._normalize_case_id(case_id),
            "filenames": cls._normalize_filenames(filenames),
            "frame_interval_seconds": float(frame_interval_seconds),
            "batch_size": int(batch_size),
            "force": bool(force),
            "metadata": payload_metadata,
        }

    @staticmethod
    def _dedupe_key(payload: dict[str, Any]) -> str:
        canonical = {
            "case_id": str(payload.get("case_id") or "").strip(),
            "job_kind": str(payload.get("job_kind") or "").strip().lower(),
            "filenames": sorted(
                [str(item or "").strip() for item in (payload.get("filenames") or []) if str(item or "").strip()]
            ),
            "frame_interval_seconds": round(float(payload.get("frame_interval_seconds", 1.0)), 6),
            "batch_size": int(payload.get("batch_size", 32)),
            "force": bool(payload.get("force", False)),
            "metadata": payload.get("metadata")
            if isinstance(payload.get("metadata"), dict)
            else {},
        }
        encoded = json.dumps(canonical, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> dict[str, Any]:
        try:
            payload = json.loads(str(row["payload_json"]))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "job_id": int(row["id"]),
            "case_id": str(row["case_id"] or ""),
            "job_kind": str(row["job_kind"] or "semantic_index"),
            "priority": int(row["priority"] or 50),
            "status": str(row["status"] or ""),
            "error": str(row["error"] or ""),
            "attempt_count": int(row["attempt_count"] or 0),
            "enqueued_at": str(row["enqueued_at"] or ""),
            "started_at": str(row["started_at"] or ""),
            "finished_at": str(row["finished_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
            "payload": payload,
            "dedupe_key": str(row["dedupe_key"] or ""),
        }

    def enqueue_or_get_active(
        self,
        *,
        case_id: str,
        filenames: list[str],
        frame_interval_seconds: float,
        batch_size: int,
        force: bool,
        job_kind: str = DEFAULT_JOB_KIND,
        priority: int = DEFAULT_PRIORITY,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._build_payload(
            case_id=case_id,
            filenames=filenames,
            frame_interval_seconds=frame_interval_seconds,
            batch_size=batch_size,
            force=force,
            metadata=metadata,
        )
        payload["job_kind"] = self._normalize_job_kind(job_kind)
        normalized_priority = self._normalize_priority(priority)
        dedupe_key = self._dedupe_key(payload)
        now = self._utc_now_iso()

        with self._lock, self._managed_connection() as conn:
            # Dedupe exact same queued/running job
            existing = conn.execute(
                """
                SELECT *
                FROM index_job_queue
                WHERE dedupe_key = ?
                  AND status IN ('queued', 'running')
                ORDER BY id ASC
                LIMIT 1
                """,
                (dedupe_key,),
            ).fetchone()
            if existing is not None:
                job = self._row_to_job(existing)
                job["created"] = False
                job["reason"] = "duplicate_active_job"
                job["queue_position"] = self.queue_position(job["job_id"], _conn=conn)
                return job

            # Prefer appending into an already queued job for the same case/kind.
            # We intentionally do not append into a running job because the worker
            # may be processing one file at a time (interleaving mode).
            case_active = conn.execute(
                """
                SELECT *
                FROM index_job_queue
                WHERE case_id = ?
                  AND job_kind = ?
                  AND status = 'queued'
                ORDER BY priority ASC, id ASC
                LIMIT 1
                """,
                (payload["case_id"], payload["job_kind"]),
            ).fetchone()
            if case_active is not None:
                active_job = self._row_to_job(case_active)
                active_payload = active_job.get("payload") if isinstance(active_job.get("payload"), dict) else {}
                try:
                    existing_files = self._normalize_filenames(active_payload.get("filenames") or [])
                except ValueError:
                    existing_files = []
                incoming_files = self._normalize_filenames(payload.get("filenames") or [])
                merged_files, appended_files = self._merge_unique_filenames(existing_files, incoming_files)

                if not appended_files:
                    active_job["created"] = False
                    active_job["reason"] = "case_already_has_active_job"
                    active_job["appended_count"] = 0
                    active_job["appended_filenames"] = []
                    active_job["queue_position"] = self.queue_position(active_job["job_id"], _conn=conn)
                    return active_job

                merged_payload = {
                    "case_id": payload["case_id"],
                    "job_kind": payload["job_kind"],
                    "filenames": merged_files,
                    "frame_interval_seconds": float(
                        active_payload.get("frame_interval_seconds", payload["frame_interval_seconds"])
                    ),
                    "batch_size": int(active_payload.get("batch_size", payload["batch_size"])),
                    "force": bool(active_payload.get("force", payload["force"])),
                    "metadata": {},
                }
                active_metadata = (
                    active_payload.get("metadata")
                    if isinstance(active_payload.get("metadata"), dict)
                    else {}
                )
                incoming_metadata = (
                    payload.get("metadata")
                    if isinstance(payload.get("metadata"), dict)
                    else {}
                )
                merged_metadata = {**active_metadata, **incoming_metadata}
                if (
                    "analysis_face_people" in active_metadata
                    or "analysis_face_people" in incoming_metadata
                ):
                    merged_metadata["analysis_face_people"] = bool(
                        active_metadata.get("analysis_face_people", False)
                    ) or bool(incoming_metadata.get("analysis_face_people", False))
                if (
                    "analysis_vehicles" in active_metadata
                    or "analysis_vehicles" in incoming_metadata
                ):
                    merged_metadata["analysis_vehicles"] = bool(
                        active_metadata.get("analysis_vehicles", False)
                    ) or bool(incoming_metadata.get("analysis_vehicles", False))
                for key in (
                    "analysis_face_people_filenames",
                    "analysis_vehicles_filenames",
                ):
                    if key not in active_metadata and key not in incoming_metadata:
                        continue
                    active_files_raw = active_metadata.get(key) or []
                    incoming_files_raw = incoming_metadata.get(key) or []
                    try:
                        active_files = self._normalize_filenames(active_files_raw)
                    except ValueError:
                        active_files = []
                    try:
                        incoming_files = self._normalize_filenames(incoming_files_raw)
                    except ValueError:
                        incoming_files = []
                    merged_files_for_key, _ = self._merge_unique_filenames(
                        active_files,
                        incoming_files,
                    )
                    if merged_files_for_key:
                        merged_metadata[key] = merged_files_for_key
                    else:
                        merged_metadata.pop(key, None)
                merged_payload["metadata"] = merged_metadata
                merged_dedupe_key = self._dedupe_key(merged_payload)
                conn.execute(
                    """
                    UPDATE index_job_queue
                    SET payload_json = ?,
                        dedupe_key = ?,
                        priority = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(merged_payload, ensure_ascii=True),
                        merged_dedupe_key,
                        normalized_priority,
                        now,
                        int(active_job["job_id"]),
                    ),
                )
                row = conn.execute(
                    """
                    SELECT *
                    FROM index_job_queue
                    WHERE id = ?
                    """,
                    (int(active_job["job_id"]),),
                ).fetchone()
                conn.commit()
                job = self._row_to_job(row) if row is not None else active_job
                job["created"] = False
                job["reason"] = "appended_case_active_job"
                job["appended_count"] = len(appended_files)
                job["appended_filenames"] = appended_files
                job["queue_position"] = self.queue_position(job["job_id"], _conn=conn)
                return job

            conn.execute(
                """
                INSERT INTO index_job_queue(
                    case_id, job_kind, priority, dedupe_key, payload_json, status, error,
                    enqueued_at, started_at, finished_at, updated_at, attempt_count
                )
                VALUES (?, ?, ?, ?, ?, 'queued', '', ?, '', '', ?, 0)
                """,
                (
                    payload["case_id"],
                    payload["job_kind"],
                    normalized_priority,
                    dedupe_key,
                    json.dumps(payload, ensure_ascii=True),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT *
                FROM index_job_queue
                WHERE id = last_insert_rowid()
                """
            ).fetchone()
            conn.commit()
            job = self._row_to_job(row)
            job["created"] = True
            job["reason"] = "queued"
            job["queue_position"] = self.queue_position(job["job_id"], _conn=conn)
            return job

    def queue_position(self, job_id: int, *, _conn: sqlite3.Connection | None = None) -> int:
        own_connection = _conn is None
        conn = _conn if _conn is not None else self._connect()
        try:
            job_row = conn.execute(
                """
                SELECT id, priority
                FROM index_job_queue
                WHERE id = ?
                """,
                (int(job_id),),
            ).fetchone()
            if job_row is None:
                return 0
            current_priority = int(job_row["priority"] or self.DEFAULT_PRIORITY)
            row = conn.execute(
                """
                SELECT COUNT(*) AS ahead
                FROM index_job_queue
                WHERE status = 'queued'
                  AND (
                    priority < ?
                    OR (priority = ? AND id < ?)
                  )
                """,
                (current_priority, current_priority, int(job_id)),
            ).fetchone()
            if row is None:
                return 0
            return max(0, int(row["ahead"] or 0))
        finally:
            if own_connection:
                conn.close()

    def claim_next_queued(
        self,
        *,
        job_kinds: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, Any] | None:
        now = self._utc_now_iso()
        normalized_job_kinds = self._normalize_job_kinds(job_kinds)
        with self._lock, self._managed_connection() as conn:
            if normalized_job_kinds:
                placeholders = ",".join(["?"] * len(normalized_job_kinds))
                row = conn.execute(
                    f"""
                    SELECT *
                    FROM index_job_queue
                    WHERE status = 'queued'
                      AND job_kind IN ({placeholders})
                    ORDER BY priority ASC, id ASC
                    LIMIT 1
                    """,
                    tuple(normalized_job_kinds),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT *
                    FROM index_job_queue
                    WHERE status = 'queued'
                    ORDER BY priority ASC, id ASC
                    LIMIT 1
                    """
                ).fetchone()
            if row is None:
                return None

            job_id = int(row["id"])
            conn.execute(
                """
                UPDATE index_job_queue
                SET status = 'running',
                    started_at = CASE WHEN started_at = '' THEN ? ELSE started_at END,
                    updated_at = ?,
                    attempt_count = attempt_count + 1
                WHERE id = ?
                  AND status = 'queued'
                """,
                (now, now, job_id),
            )
            if int(conn.total_changes) == 0:
                conn.commit()
                return None

            updated = conn.execute(
                """
                SELECT *
                FROM index_job_queue
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            conn.commit()
            return self._row_to_job(updated) if updated is not None else None

    def complete_job(self, *, job_id: int, status: str, error: str = "") -> dict[str, Any] | None:
        next_status = str(status or "").strip().lower()
        if next_status not in {"completed", "failed", "cancelled", "interrupted"}:
            raise ValueError("Invalid completion status")
        now = self._utc_now_iso()
        clean_error = str(error or "").strip()

        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                UPDATE index_job_queue
                SET status = ?,
                    error = ?,
                    finished_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (next_status, clean_error, now, now, int(job_id)),
            )
            row = conn.execute(
                """
                SELECT *
                FROM index_job_queue
                WHERE id = ?
                """,
                (int(job_id),),
            ).fetchone()
            conn.commit()
            return self._row_to_job(row) if row is not None else None

    def get_case_active(self, case_id: str, *, job_kind: str | None = None) -> dict[str, Any] | None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_job_kind = (
            self._normalize_job_kind(job_kind)
            if job_kind is not None and str(job_kind).strip()
            else ""
        )
        with self._lock, self._managed_connection() as conn:
            if normalized_job_kind:
                row = conn.execute(
                    """
                    SELECT *
                    FROM index_job_queue
                    WHERE case_id = ?
                      AND job_kind = ?
                      AND status IN ('queued', 'running')
                    ORDER BY
                      CASE status WHEN 'running' THEN 0 ELSE 1 END ASC,
                      priority ASC,
                      id ASC
                    LIMIT 1
                    """,
                    (normalized_case_id, normalized_job_kind),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT *
                    FROM index_job_queue
                    WHERE case_id = ?
                      AND status IN ('queued', 'running')
                    ORDER BY
                      CASE status WHEN 'running' THEN 0 ELSE 1 END ASC,
                      priority ASC,
                      id ASC
                    LIMIT 1
                    """,
                    (normalized_case_id,),
                ).fetchone()
            if row is None:
                return None
            job = self._row_to_job(row)
            job["queue_position"] = self.queue_position(job["job_id"], _conn=conn)
            return job

    def get_case_latest(self, case_id: str, *, job_kind: str | None = None) -> dict[str, Any] | None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_job_kind = (
            self._normalize_job_kind(job_kind)
            if job_kind is not None and str(job_kind).strip()
            else ""
        )
        with self._lock, self._managed_connection() as conn:
            if normalized_job_kind:
                row = conn.execute(
                    """
                    SELECT *
                    FROM index_job_queue
                    WHERE case_id = ?
                      AND job_kind = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (normalized_case_id, normalized_job_kind),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT *
                    FROM index_job_queue
                    WHERE case_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (normalized_case_id,),
                ).fetchone()
            if row is None:
                return None
            job = self._row_to_job(row)
            job_status = str(job.get("status") or "").strip().lower()
            if job_status == "queued":
                job["queue_position"] = self.queue_position(job["job_id"], _conn=conn)
            else:
                job["queue_position"] = 0
            return job

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock, self._managed_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM index_job_queue
                WHERE id = ?
                """,
                (int(job_id),),
            ).fetchone()
            if row is None:
                return None
            job = self._row_to_job(row)
            job["queue_position"] = self.queue_position(job["job_id"], _conn=conn)
            return job

    def mark_running_jobs_interrupted(self) -> int:
        now = self._utc_now_iso()
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                UPDATE index_job_queue
                SET status = 'interrupted',
                    error = CASE
                        WHEN error = '' THEN 'Marked interrupted on startup.'
                        ELSE error
                    END,
                    finished_at = CASE
                        WHEN finished_at = '' THEN ?
                        ELSE finished_at
                    END,
                    updated_at = ?
                WHERE status = 'running'
                """,
                (now, now),
            )
            changed = int(conn.total_changes)
            conn.commit()
            return changed

    def recover_running_jobs_to_queued(self) -> int:
        """Re-queue in-flight jobs on startup after an unclean shutdown."""
        now = self._utc_now_iso()
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                UPDATE index_job_queue
                SET status = 'queued',
                    error = CASE
                        WHEN error = '' THEN 'Recovered and re-queued on startup after unclean shutdown.'
                        ELSE error
                    END,
                    started_at = '',
                    finished_at = '',
                    updated_at = ?
                WHERE status = 'running'
                """,
                (now,),
            )
            changed = int(conn.total_changes)
            conn.commit()
            return changed

    def clear_case(self, case_id: str) -> None:
        normalized_case_id = self._normalize_case_id(case_id)
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                DELETE FROM index_job_queue
                WHERE case_id = ?
                """,
                (normalized_case_id,),
            )
            conn.commit()

    def cancel_case_active(
        self,
        case_id: str,
        *,
        reason: str = "Cancelled by user request.",
        job_kind: str | None = None,
    ) -> int:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_job_kind = (
            self._normalize_job_kind(job_kind)
            if job_kind is not None and str(job_kind).strip()
            else ""
        )
        now = self._utc_now_iso()
        clean_reason = str(reason or "").strip() or "Cancelled by user request."

        with self._lock, self._managed_connection() as conn:
            if normalized_job_kind:
                conn.execute(
                    """
                    UPDATE index_job_queue
                    SET status = 'cancelled',
                        error = CASE
                            WHEN error = '' THEN ?
                            ELSE error
                        END,
                        finished_at = CASE
                            WHEN finished_at = '' THEN ?
                            ELSE finished_at
                        END,
                        updated_at = ?
                    WHERE case_id = ?
                      AND job_kind = ?
                      AND status IN ('queued', 'running')
                    """,
                    (
                        clean_reason,
                        now,
                        now,
                        normalized_case_id,
                        normalized_job_kind,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE index_job_queue
                    SET status = 'cancelled',
                        error = CASE
                            WHEN error = '' THEN ?
                            ELSE error
                        END,
                        finished_at = CASE
                            WHEN finished_at = '' THEN ?
                            ELSE finished_at
                        END,
                        updated_at = ?
                    WHERE case_id = ?
                      AND status IN ('queued', 'running')
                    """,
                    (
                        clean_reason,
                        now,
                        now,
                        normalized_case_id,
                    ),
                )
            changed = int(conn.total_changes)
            conn.commit()
            return changed

    def list_active_jobs(self, *, limit: int = 200) -> list[dict[str, Any]]:
        safe_limit = max(1, min(5000, int(limit or 0)))
        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM index_job_queue
                WHERE status IN ('queued', 'running')
                ORDER BY priority ASC, id ASC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            jobs = [self._row_to_job(row) for row in rows]
            for job in jobs:
                job["queue_position"] = self.queue_position(int(job.get("job_id", 0)), _conn=conn)
            return jobs

    def delete_jobs(
        self,
        job_ids: list[int] | tuple[int, ...] | set[int],
        *,
        cancel_running: bool = True,
        reason: str = "Removed from queue by user request.",
    ) -> dict[str, Any]:
        unique_job_ids: list[int] = []
        seen: set[int] = set()
        for raw in job_ids:
            try:
                parsed = int(raw)
            except Exception:
                continue
            if parsed <= 0 or parsed in seen:
                continue
            seen.add(parsed)
            unique_job_ids.append(parsed)

        if not unique_job_ids:
            return {
                "requested_count": 0,
                "found_count": 0,
                "removed_count": 0,
                "cancelled_running_count": 0,
                "skipped_running_count": 0,
                "not_found_ids": [],
                "removed_job_ids": [],
                "cancelled_running_job_ids": [],
                "skipped_running_job_ids": [],
                "affected_case_ids": [],
            }

        safe_reason = str(reason or "").strip() or "Removed from queue by user request."
        now = self._utc_now_iso()
        placeholders = ",".join(["?"] * len(unique_job_ids))

        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, case_id, status
                FROM index_job_queue
                WHERE id IN ({placeholders})
                """,
                tuple(unique_job_ids),
            ).fetchall()

            by_id = {int(row["id"]): row for row in rows}
            not_found_ids = [job_id for job_id in unique_job_ids if job_id not in by_id]

            removed_job_ids: list[int] = []
            cancelled_running_job_ids: list[int] = []
            skipped_running_job_ids: list[int] = []
            affected_case_ids: set[str] = set()

            for job_id in unique_job_ids:
                row = by_id.get(job_id)
                if row is None:
                    continue
                status = str(row["status"] or "").strip().lower()
                case_id = str(row["case_id"] or "").strip()
                if case_id:
                    affected_case_ids.add(case_id)

                if status == "running":
                    if not bool(cancel_running):
                        skipped_running_job_ids.append(job_id)
                        continue
                    conn.execute(
                        """
                        UPDATE index_job_queue
                        SET status = 'cancelled',
                            error = CASE
                                WHEN error = '' THEN ?
                                ELSE error
                            END,
                            finished_at = CASE
                                WHEN finished_at = '' THEN ?
                                ELSE finished_at
                            END,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (safe_reason, now, now, int(job_id)),
                    )
                    cancelled_running_job_ids.append(job_id)
                    continue

                conn.execute(
                    """
                    DELETE FROM index_job_queue
                    WHERE id = ?
                    """,
                    (int(job_id),),
                )
                removed_job_ids.append(job_id)

            conn.commit()

        return {
            "requested_count": len(unique_job_ids),
            "found_count": len(rows),
            "removed_count": len(removed_job_ids),
            "cancelled_running_count": len(cancelled_running_job_ids),
            "skipped_running_count": len(skipped_running_job_ids),
            "not_found_ids": not_found_ids,
            "removed_job_ids": removed_job_ids,
            "cancelled_running_job_ids": cancelled_running_job_ids,
            "skipped_running_job_ids": skipped_running_job_ids,
            "affected_case_ids": sorted(affected_case_ids),
        }
