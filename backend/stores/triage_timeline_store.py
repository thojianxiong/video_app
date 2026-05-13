from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class TriageTimelineStore:
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
                CREATE TABLE IF NOT EXISTS triage_timeline_cache (
                    case_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    bucket_key TEXT NOT NULL,
                    bucket_seconds REAL NOT NULL,
                    video_signature TEXT NOT NULL,
                    analysis_signature TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (case_id, filename, bucket_key)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_triage_timeline_cache_case_updated
                ON triage_timeline_cache(case_id, updated_at DESC, filename ASC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_triage_timeline_cache_video_signature
                ON triage_timeline_cache(case_id, filename, bucket_key, video_signature)
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

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        normalized = str(filename or "").strip()
        if not normalized:
            raise ValueError("filename is required")
        return normalized

    @staticmethod
    def _normalize_signature(value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    def _normalize_bucket_seconds(bucket_seconds: float) -> float:
        try:
            safe_value = float(bucket_seconds)
        except Exception as exc:
            raise ValueError("bucket_seconds must be a number") from exc
        if safe_value <= 0:
            raise ValueError("bucket_seconds must be > 0")
        return float(safe_value)

    @classmethod
    def _bucket_key(cls, bucket_seconds: float) -> str:
        safe_bucket_seconds = cls._normalize_bucket_seconds(bucket_seconds)
        return f"{safe_bucket_seconds:.3f}"

    @staticmethod
    def _decode_payload(raw_payload: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(str(raw_payload))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return dict(payload)

    def load_payload_exact(
        self,
        *,
        case_id: str,
        filename: str,
        bucket_seconds: float,
        video_signature: str,
        analysis_signature: str,
    ) -> dict[str, Any] | None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        safe_bucket_seconds = self._normalize_bucket_seconds(bucket_seconds)
        safe_bucket_key = self._bucket_key(safe_bucket_seconds)
        safe_video_signature = self._normalize_signature(video_signature, "video_signature")
        safe_analysis_signature = self._normalize_signature(
            analysis_signature,
            "analysis_signature",
        )

        with self._lock, self._managed_connection() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM triage_timeline_cache
                WHERE case_id = ?
                  AND filename = ?
                  AND bucket_key = ?
                  AND video_signature = ?
                  AND analysis_signature = ?
                LIMIT 1
                """,
                (
                    normalized_case_id,
                    normalized_filename,
                    safe_bucket_key,
                    safe_video_signature,
                    safe_analysis_signature,
                ),
            ).fetchone()
        if row is None:
            return None
        return self._decode_payload(str(row["payload_json"]))

    def load_payload_stale_for_video(
        self,
        *,
        case_id: str,
        filename: str,
        bucket_seconds: float,
        video_signature: str,
    ) -> dict[str, Any] | None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        safe_bucket_seconds = self._normalize_bucket_seconds(bucket_seconds)
        safe_bucket_key = self._bucket_key(safe_bucket_seconds)
        safe_video_signature = self._normalize_signature(video_signature, "video_signature")

        with self._lock, self._managed_connection() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM triage_timeline_cache
                WHERE case_id = ?
                  AND filename = ?
                  AND bucket_key = ?
                  AND video_signature = ?
                LIMIT 1
                """,
                (
                    normalized_case_id,
                    normalized_filename,
                    safe_bucket_key,
                    safe_video_signature,
                ),
            ).fetchone()
        if row is None:
            return None
        return self._decode_payload(str(row["payload_json"]))

    def upsert_payload(
        self,
        *,
        case_id: str,
        filename: str,
        bucket_seconds: float,
        video_signature: str,
        analysis_signature: str,
        payload: dict[str, Any],
    ) -> None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        safe_bucket_seconds = self._normalize_bucket_seconds(bucket_seconds)
        safe_bucket_key = self._bucket_key(safe_bucket_seconds)
        safe_video_signature = self._normalize_signature(video_signature, "video_signature")
        safe_analysis_signature = self._normalize_signature(
            analysis_signature,
            "analysis_signature",
        )
        safe_payload = dict(payload) if isinstance(payload, dict) else {}
        now = self._utc_now_iso()

        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                INSERT INTO triage_timeline_cache(
                    case_id,
                    filename,
                    bucket_key,
                    bucket_seconds,
                    video_signature,
                    analysis_signature,
                    payload_json,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id, filename, bucket_key) DO UPDATE SET
                    bucket_seconds = excluded.bucket_seconds,
                    video_signature = excluded.video_signature,
                    analysis_signature = excluded.analysis_signature,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_case_id,
                    normalized_filename,
                    safe_bucket_key,
                    float(safe_bucket_seconds),
                    safe_video_signature,
                    safe_analysis_signature,
                    json.dumps(safe_payload, ensure_ascii=True),
                    now,
                ),
            )
            conn.commit()

    def delete_video(self, *, case_id: str, filename: str) -> None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                DELETE FROM triage_timeline_cache
                WHERE case_id = ? AND filename = ?
                """,
                (normalized_case_id, normalized_filename),
            )
            conn.commit()

    def delete_case(self, case_id: str) -> None:
        normalized_case_id = self._normalize_case_id(case_id)
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                DELETE FROM triage_timeline_cache
                WHERE case_id = ?
                """,
                (normalized_case_id,),
            )
            conn.commit()
