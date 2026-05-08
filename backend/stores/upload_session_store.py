from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class UploadSessionStore:
    SESSION_STATUSES = {"active", "completed", "completed_with_errors", "failed", "cancelled"}
    FILE_STATUSES = {"pending", "in_progress", "ready", "completed", "failed", "cancelled"}

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
                CREATE TABLE IF NOT EXISTS upload_sessions (
                    session_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    chunk_size_bytes INTEGER NOT NULL,
                    file_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_session_files (
                    file_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    source_index INTEGER NOT NULL,
                    source_filename TEXT NOT NULL,
                    source_size INTEGER NOT NULL DEFAULT 0,
                    source_last_modified_ms INTEGER NOT NULL DEFAULT 0,
                    source_key TEXT NOT NULL,
                    source_extension TEXT NOT NULL DEFAULT '',
                    temp_upload_path TEXT NOT NULL,
                    chunk_size_bytes INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    received_bytes INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    uploaded_filename TEXT NOT NULL DEFAULT '',
                    converted_to_mp4 INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES upload_sessions(session_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_session_chunks (
                    file_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (file_id, chunk_index),
                    FOREIGN KEY(file_id) REFERENCES upload_session_files(file_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_upload_session_files_session
                ON upload_session_files(session_id, source_index)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_upload_session_chunks_file
                ON upload_session_chunks(file_id, chunk_index)
                """
            )
            conn.commit()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_session_id(session_id: str) -> str:
        normalized = str(session_id or "").strip()
        if not normalized:
            raise ValueError("session_id is required")
        return normalized

    @staticmethod
    def _normalize_case_id(case_id: str) -> str:
        normalized = str(case_id or "").strip()
        if not normalized:
            raise ValueError("case_id is required")
        return normalized

    @staticmethod
    def _normalize_file_id(file_id: str) -> str:
        normalized = str(file_id or "").strip()
        if not normalized:
            raise ValueError("file_id is required")
        return normalized

    @staticmethod
    def _normalize_chunk_index(chunk_index: int) -> int:
        value = int(chunk_index)
        if value < 0:
            raise ValueError("chunk_index must be >= 0")
        return value

    @staticmethod
    def _normalize_chunk_size(chunk_size_bytes: int) -> int:
        value = int(chunk_size_bytes)
        if value <= 0:
            raise ValueError("chunk_size_bytes must be > 0")
        return value

    @classmethod
    def _normalize_session_status(cls, status: str) -> str:
        value = str(status or "").strip().lower()
        if value not in cls.SESSION_STATUSES:
            raise ValueError(f"invalid session status: {status}")
        return value

    @classmethod
    def _normalize_file_status(cls, status: str) -> str:
        value = str(status or "").strip().lower()
        if value not in cls.FILE_STATUSES:
            raise ValueError(f"invalid file status: {status}")
        return value

    @staticmethod
    def _coerce_file_payload(row: sqlite3.Row) -> dict[str, Any]:
        source_size = max(0, int(row["source_size"] or 0))
        received_bytes = max(0, min(source_size, int(row["received_bytes"] or 0)))
        total_chunks = max(1, int(row["total_chunks"] or 1))
        received_chunks = max(0, int(row["received_chunks"] or 0))
        progress_percent = 100.0
        if source_size > 0:
            progress_percent = max(
                0.0,
                min(100.0, (float(received_bytes) / float(source_size)) * 100.0),
            )
        elif total_chunks > 0:
            progress_percent = max(
                0.0,
                min(100.0, (float(received_chunks) / float(total_chunks)) * 100.0),
            )

        return {
            "file_id": str(row["file_id"] or ""),
            "session_id": str(row["session_id"] or ""),
            "source_index": int(row["source_index"] or 0),
            "source_filename": str(row["source_filename"] or ""),
            "source_size": source_size,
            "source_last_modified_ms": int(row["source_last_modified_ms"] or 0),
            "source_key": str(row["source_key"] or ""),
            "source_extension": str(row["source_extension"] or ""),
            "temp_upload_path": str(row["temp_upload_path"] or ""),
            "chunk_size_bytes": max(1, int(row["chunk_size_bytes"] or 1)),
            "total_chunks": total_chunks,
            "received_chunks": received_chunks,
            "received_bytes": received_bytes,
            "status": str(row["status"] or "pending"),
            "uploaded_filename": str(row["uploaded_filename"] or ""),
            "converted_to_mp4": bool(int(row["converted_to_mp4"] or 0)),
            "error": str(row["error"] or ""),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
            "progress_percent": progress_percent,
        }

    def _load_session_files_locked(
        self,
        conn: sqlite3.Connection,
        session_id: str,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
                f.*,
                COALESCE(chunks.received_chunks, 0) AS received_chunks
            FROM upload_session_files AS f
            LEFT JOIN (
                SELECT file_id, COUNT(*) AS received_chunks
                FROM upload_session_chunks
                GROUP BY file_id
            ) AS chunks
            ON chunks.file_id = f.file_id
            WHERE f.session_id = ?
            ORDER BY f.source_index ASC, f.file_id ASC
            """,
            (session_id,),
        ).fetchall()
        return [self._coerce_file_payload(row) for row in rows]

    def _load_session_locked(
        self,
        conn: sqlite3.Connection,
        session_id: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT *
            FROM upload_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None

        files = self._load_session_files_locked(conn, session_id)
        total_bytes = sum(max(0, int(item.get("source_size", 0))) for item in files)
        received_bytes = sum(max(0, int(item.get("received_bytes", 0))) for item in files)
        completed_files = sum(1 for item in files if str(item.get("status") or "") == "completed")
        failed_files = sum(1 for item in files if str(item.get("status") or "") == "failed")
        all_chunks_received = all(
            int(item.get("received_chunks", 0)) >= int(item.get("total_chunks", 0))
            for item in files
        ) if files else False

        progress_percent = 100.0
        if total_bytes > 0:
            progress_percent = max(
                0.0,
                min(100.0, (float(received_bytes) / float(total_bytes)) * 100.0),
            )
        elif files:
            file_fraction = sum(
                float(item.get("progress_percent", 0.0)) for item in files
            ) / float(len(files))
            progress_percent = max(0.0, min(100.0, file_fraction))

        return {
            "session_id": str(row["session_id"] or ""),
            "case_id": str(row["case_id"] or ""),
            "status": str(row["status"] or "active"),
            "chunk_size_bytes": max(1, int(row["chunk_size_bytes"] or 1)),
            "file_count": max(0, int(row["file_count"] or 0)),
            "error": str(row["error"] or ""),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
            "total_bytes": total_bytes,
            "received_bytes": received_bytes,
            "progress_percent": progress_percent,
            "completed_files": completed_files,
            "failed_files": failed_files,
            "all_chunks_received": all_chunks_received,
            "files": files,
        }

    def create_session(
        self,
        *,
        session_id: str,
        case_id: str,
        chunk_size_bytes: int,
        files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_chunk_size = self._normalize_chunk_size(chunk_size_bytes)
        if not isinstance(files, list) or not files:
            raise ValueError("files are required")

        now = self._utc_now_iso()
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                INSERT INTO upload_sessions(
                    session_id, case_id, status, chunk_size_bytes, file_count, error, created_at, updated_at
                ) VALUES (?, ?, 'active', ?, ?, '', ?, ?)
                """,
                (
                    normalized_session_id,
                    normalized_case_id,
                    normalized_chunk_size,
                    len(files),
                    now,
                    now,
                ),
            )

            for item in files:
                file_id = self._normalize_file_id(str(item.get("file_id") or ""))
                source_index = max(0, int(item.get("source_index", 0)))
                source_filename = str(item.get("source_filename") or "").strip()
                source_size = max(0, int(item.get("source_size", 0)))
                source_last_modified_ms = max(0, int(item.get("source_last_modified_ms", 0)))
                source_key = str(item.get("source_key") or "").strip()
                source_extension = str(item.get("source_extension") or "").strip()
                temp_upload_path = str(item.get("temp_upload_path") or "").strip()
                if not source_filename:
                    raise ValueError("source_filename is required")
                if not source_key:
                    source_key = json.dumps(
                        [source_filename, source_size, source_last_modified_ms],
                        ensure_ascii=True,
                    )
                if not temp_upload_path:
                    raise ValueError("temp_upload_path is required")
                total_chunks = max(1, int(math.ceil(float(source_size) / float(normalized_chunk_size))))
                conn.execute(
                    """
                    INSERT INTO upload_session_files(
                        file_id, session_id, source_index, source_filename, source_size,
                        source_last_modified_ms, source_key, source_extension, temp_upload_path,
                        chunk_size_bytes, total_chunks, received_bytes, status, uploaded_filename,
                        converted_to_mp4, error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'pending', '', 0, '', ?, ?)
                    """,
                    (
                        file_id,
                        normalized_session_id,
                        source_index,
                        source_filename,
                        source_size,
                        source_last_modified_ms,
                        source_key,
                        source_extension,
                        temp_upload_path,
                        normalized_chunk_size,
                        total_chunks,
                        now,
                        now,
                    ),
                )
            conn.commit()
            payload = self._load_session_locked(conn, normalized_session_id)
        if payload is None:
            raise RuntimeError("failed to create upload session")
        return payload

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        normalized_session_id = self._normalize_session_id(session_id)
        with self._lock, self._managed_connection() as conn:
            return self._load_session_locked(conn, normalized_session_id)

    def get_session_file(self, session_id: str, file_id: str) -> dict[str, Any] | None:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_file_id = self._normalize_file_id(file_id)
        with self._lock, self._managed_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    f.*,
                    COALESCE(chunks.received_chunks, 0) AS received_chunks
                FROM upload_session_files AS f
                LEFT JOIN (
                    SELECT file_id, COUNT(*) AS received_chunks
                    FROM upload_session_chunks
                    GROUP BY file_id
                ) AS chunks
                ON chunks.file_id = f.file_id
                WHERE f.session_id = ? AND f.file_id = ?
                """,
                (normalized_session_id, normalized_file_id),
            ).fetchone()
            if row is None:
                return None
            return self._coerce_file_payload(row)

    def has_chunk(self, file_id: str, chunk_index: int) -> bool:
        normalized_file_id = self._normalize_file_id(file_id)
        normalized_chunk_index = self._normalize_chunk_index(chunk_index)
        with self._lock, self._managed_connection() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM upload_session_chunks
                WHERE file_id = ? AND chunk_index = ?
                """,
                (normalized_file_id, normalized_chunk_index),
            ).fetchone()
            return row is not None

    def record_chunk(
        self,
        *,
        session_id: str,
        file_id: str,
        chunk_index: int,
        chunk_size_bytes: int,
        total_chunks: int | None = None,
    ) -> dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_file_id = self._normalize_file_id(file_id)
        normalized_chunk_index = self._normalize_chunk_index(chunk_index)
        normalized_chunk_size = max(0, int(chunk_size_bytes))
        requested_total_chunks = max(1, int(total_chunks or 1))
        now = self._utc_now_iso()

        with self._lock, self._managed_connection() as conn:
            file_row = conn.execute(
                """
                SELECT *
                FROM upload_session_files
                WHERE session_id = ? AND file_id = ?
                """,
                (normalized_session_id, normalized_file_id),
            ).fetchone()
            if file_row is None:
                raise KeyError("upload session file not found")

            file_status = str(file_row["status"] or "pending")
            if file_status in {"completed", "failed", "cancelled"}:
                current = self._load_session_locked(conn, normalized_session_id)
                file_payload = None
                if current:
                    for item in current.get("files", []):
                        if str(item.get("file_id") or "") == normalized_file_id:
                            file_payload = item
                            break
                return {
                    "inserted": False,
                    "file": file_payload,
                    "session": current,
                }

            insert_cursor = conn.execute(
                """
                INSERT OR IGNORE INTO upload_session_chunks(
                    file_id, chunk_index, chunk_size_bytes, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (normalized_file_id, normalized_chunk_index, normalized_chunk_size, now),
            )
            inserted = int(insert_cursor.rowcount or 0) > 0

            if inserted:
                conn.execute(
                    """
                    UPDATE upload_session_files
                    SET
                        received_bytes = MIN(source_size, received_bytes + ?),
                        total_chunks = MAX(total_chunks, ?),
                        status = CASE WHEN status = 'pending' THEN 'in_progress' ELSE status END,
                        updated_at = ?
                    WHERE file_id = ?
                    """,
                    (
                        normalized_chunk_size,
                        requested_total_chunks,
                        now,
                        normalized_file_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE upload_sessions
                    SET
                        status = CASE WHEN status = 'active' THEN 'active' ELSE status END,
                        updated_at = ?
                    WHERE session_id = ?
                    """,
                    (now, normalized_session_id),
                )

            # Promote file to "ready" once all chunks are present.
            file_ready_row = conn.execute(
                """
                SELECT
                    f.*,
                    COALESCE(chunks.received_chunks, 0) AS received_chunks
                FROM upload_session_files AS f
                LEFT JOIN (
                    SELECT file_id, COUNT(*) AS received_chunks
                    FROM upload_session_chunks
                    GROUP BY file_id
                ) AS chunks
                ON chunks.file_id = f.file_id
                WHERE f.file_id = ?
                """,
                (normalized_file_id,),
            ).fetchone()
            if file_ready_row is not None:
                source_size = max(0, int(file_ready_row["source_size"] or 0))
                received_bytes = max(0, int(file_ready_row["received_bytes"] or 0))
                file_total_chunks = max(1, int(file_ready_row["total_chunks"] or 1))
                file_received_chunks = max(0, int(file_ready_row["received_chunks"] or 0))
                file_status_now = str(file_ready_row["status"] or "pending")
                is_ready = (
                    file_received_chunks >= file_total_chunks
                    and (source_size == 0 or received_bytes >= source_size)
                )
                if is_ready and file_status_now in {"pending", "in_progress"}:
                    conn.execute(
                        """
                        UPDATE upload_session_files
                        SET status = 'ready', updated_at = ?
                        WHERE file_id = ?
                        """,
                        (now, normalized_file_id),
                    )

            conn.commit()
            session_payload = self._load_session_locked(conn, normalized_session_id)
            file_payload = None
            if session_payload:
                for item in session_payload.get("files", []):
                    if str(item.get("file_id") or "") == normalized_file_id:
                        file_payload = item
                        break

        return {
            "inserted": inserted,
            "file": file_payload,
            "session": session_payload,
        }

    def update_file_status(
        self,
        *,
        session_id: str,
        file_id: str,
        status: str,
        uploaded_filename: str = "",
        converted_to_mp4: bool = False,
        error: str = "",
    ) -> dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_file_id = self._normalize_file_id(file_id)
        normalized_status = self._normalize_file_status(status)
        now = self._utc_now_iso()
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                UPDATE upload_session_files
                SET
                    status = ?,
                    uploaded_filename = ?,
                    converted_to_mp4 = ?,
                    error = ?,
                    updated_at = ?
                WHERE session_id = ? AND file_id = ?
                """,
                (
                    normalized_status,
                    str(uploaded_filename or ""),
                    1 if bool(converted_to_mp4) else 0,
                    str(error or ""),
                    now,
                    normalized_session_id,
                    normalized_file_id,
                ),
            )
            conn.execute(
                """
                UPDATE upload_sessions
                SET updated_at = ?
                WHERE session_id = ?
                """,
                (now, normalized_session_id),
            )
            conn.commit()
            payload = self._load_session_locked(conn, normalized_session_id)
        if payload is None:
            raise KeyError("upload session not found")
        return payload

    def update_session_status(
        self,
        *,
        session_id: str,
        status: str,
        error: str = "",
    ) -> dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_status = self._normalize_session_status(status)
        now = self._utc_now_iso()
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                UPDATE upload_sessions
                SET
                    status = ?,
                    error = ?,
                    updated_at = ?
                WHERE session_id = ?
                """,
                (normalized_status, str(error or ""), now, normalized_session_id),
            )
            conn.commit()
            payload = self._load_session_locked(conn, normalized_session_id)
        if payload is None:
            raise KeyError("upload session not found")
        return payload

