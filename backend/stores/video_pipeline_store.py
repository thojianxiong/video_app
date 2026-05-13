from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class VideoPipelineStore:
    STAGES = (
        "ingest",
        "normalize",
        "triage",
        "base_index",
        "analysis_face_people",
        "analysis_face_identity",
        "analysis_vehicles",
        # Keep legacy stage for backward compatibility with old snapshots.
        "analysis",
    )
    STAGE_TERMINAL = {"completed", "failed", "skipped", "interrupted"}

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
                CREATE TABLE IF NOT EXISTS video_pipeline_latest (
                    case_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    snapshot_json TEXT NOT NULL,
                    PRIMARY KEY (case_id, filename)
                )
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

    @classmethod
    def _empty_stage(cls, stage_name: str) -> dict[str, Any]:
        return {
            "name": stage_name,
            "status": "pending",
            "attempts": 0,
            "started_at": "",
            "finished_at": "",
            "updated_at": "",
            "error": "",
            "details": {},
        }

    @classmethod
    def _new_snapshot(cls, case_id: str, filename: str) -> dict[str, Any]:
        now = cls._utc_now_iso()
        return {
            "case_id": case_id,
            "filename": filename,
            "overall_status": "pending",
            "current_stage": "",
            "created_at": now,
            "updated_at": now,
            "last_event": "",
            "metadata": {},
            "stages": {stage: cls._empty_stage(stage) for stage in cls.STAGES},
        }

    @classmethod
    def _coerce_snapshot(cls, case_id: str, filename: str, payload: dict | None) -> dict[str, Any]:
        snapshot = cls._new_snapshot(case_id, filename)
        if not isinstance(payload, dict):
            return snapshot

        snapshot["created_at"] = str(payload.get("created_at") or snapshot["created_at"])
        snapshot["updated_at"] = str(payload.get("updated_at") or snapshot["updated_at"])
        snapshot["last_event"] = str(payload.get("last_event") or "")
        snapshot["overall_status"] = str(payload.get("overall_status") or "pending")
        snapshot["current_stage"] = str(payload.get("current_stage") or "")

        metadata = payload.get("metadata")
        snapshot["metadata"] = dict(metadata) if isinstance(metadata, dict) else {}

        raw_stages = payload.get("stages")
        if isinstance(raw_stages, dict):
            for stage_name in cls.STAGES:
                item = raw_stages.get(stage_name)
                if not isinstance(item, dict):
                    continue
                stage = snapshot["stages"][stage_name]
                stage["status"] = str(item.get("status") or stage["status"])
                stage["attempts"] = max(0, int(item.get("attempts", stage["attempts"])))
                stage["started_at"] = str(item.get("started_at") or stage["started_at"])
                stage["finished_at"] = str(item.get("finished_at") or stage["finished_at"])
                stage["updated_at"] = str(item.get("updated_at") or stage["updated_at"])
                stage["error"] = str(item.get("error") or "")
                details = item.get("details")
                stage["details"] = dict(details) if isinstance(details, dict) else {}

        snapshot["overall_status"] = cls._derive_overall_status(snapshot)
        return snapshot

    @classmethod
    def _derive_overall_status(cls, snapshot: dict[str, Any]) -> str:
        stages = snapshot.get("stages", {})
        if not isinstance(stages, dict):
            return "pending"

        statuses = []
        for stage_name in cls.STAGES:
            stage = stages.get(stage_name)
            if not isinstance(stage, dict):
                continue
            statuses.append(str(stage.get("status") or "pending"))

        if not statuses:
            return "pending"
        if any(status == "running" for status in statuses):
            return "running"
        if any(status == "failed" for status in statuses):
            return "failed"
        if any(status == "interrupted" for status in statuses):
            return "interrupted"
        if all(status in {"completed", "skipped"} for status in statuses):
            return "completed"
        if any(status in {"completed", "skipped"} for status in statuses):
            return "partial"
        return "pending"

    def _load_snapshot_locked(self, conn: sqlite3.Connection, case_id: str, filename: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT snapshot_json
            FROM video_pipeline_latest
            WHERE case_id = ? AND filename = ?
            """,
            (case_id, filename),
        ).fetchone()
        if row is None:
            return self._new_snapshot(case_id, filename)
        try:
            payload = json.loads(str(row["snapshot_json"]))
        except Exception:
            payload = None
        return self._coerce_snapshot(case_id, filename, payload)

    def _write_snapshot_locked(self, conn: sqlite3.Connection, snapshot: dict[str, Any]) -> None:
        case_id = self._normalize_case_id(str(snapshot.get("case_id") or ""))
        filename = self._normalize_filename(str(snapshot.get("filename") or ""))
        snapshot["case_id"] = case_id
        snapshot["filename"] = filename
        snapshot["overall_status"] = self._derive_overall_status(snapshot)
        snapshot["updated_at"] = str(snapshot.get("updated_at") or self._utc_now_iso())
        encoded = json.dumps(snapshot, ensure_ascii=True)
        conn.execute(
            """
            INSERT INTO video_pipeline_latest(case_id, filename, updated_at, snapshot_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(case_id, filename) DO UPDATE SET
                updated_at = excluded.updated_at,
                snapshot_json = excluded.snapshot_json
            """,
            (case_id, filename, str(snapshot["updated_at"]), encoded),
        )

    def ensure_snapshot(self, case_id: str, filename: str) -> dict[str, Any]:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        with self._lock, self._managed_connection() as conn:
            snapshot = self._load_snapshot_locked(conn, normalized_case_id, normalized_filename)
            now = self._utc_now_iso()
            snapshot["updated_at"] = now
            if not str(snapshot.get("created_at") or "").strip():
                snapshot["created_at"] = now
            self._write_snapshot_locked(conn, snapshot)
            conn.commit()
        return snapshot

    def set_metadata(self, case_id: str, filename: str, metadata: dict[str, Any]) -> dict[str, Any]:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        clean_metadata = dict(metadata) if isinstance(metadata, dict) else {}

        with self._lock, self._managed_connection() as conn:
            snapshot = self._load_snapshot_locked(conn, normalized_case_id, normalized_filename)
            existing_metadata = snapshot.get("metadata")
            if not isinstance(existing_metadata, dict):
                existing_metadata = {}
            existing_metadata.update(clean_metadata)
            snapshot["metadata"] = existing_metadata
            snapshot["updated_at"] = self._utc_now_iso()
            self._write_snapshot_locked(conn, snapshot)
            conn.commit()
        return snapshot

    def update_stage(
        self,
        *,
        case_id: str,
        filename: str,
        stage: str,
        status: str,
        error: str = "",
        details: dict[str, Any] | None = None,
        increment_attempt: bool = False,
        event: str = "",
    ) -> dict[str, Any]:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        stage_name = str(stage or "").strip().lower()
        if stage_name not in set(self.STAGES):
            raise ValueError(f"Invalid stage: {stage}")

        next_status = str(status or "").strip().lower()
        if next_status not in {"pending", "running", "completed", "failed", "skipped", "interrupted"}:
            raise ValueError(f"Invalid stage status: {status}")

        detail_payload = dict(details) if isinstance(details, dict) else {}
        now = self._utc_now_iso()

        with self._lock, self._managed_connection() as conn:
            snapshot = self._load_snapshot_locked(conn, normalized_case_id, normalized_filename)
            stages = snapshot.setdefault("stages", {})
            if not isinstance(stages, dict):
                stages = {}
                snapshot["stages"] = stages
            stage_payload = stages.get(stage_name)
            if not isinstance(stage_payload, dict):
                stage_payload = self._empty_stage(stage_name)
                stages[stage_name] = stage_payload

            if increment_attempt:
                stage_payload["attempts"] = max(0, int(stage_payload.get("attempts", 0))) + 1
            else:
                stage_payload["attempts"] = max(0, int(stage_payload.get("attempts", 0)))

            stage_payload["status"] = next_status
            stage_payload["updated_at"] = now
            if detail_payload:
                existing_details = stage_payload.get("details")
                if not isinstance(existing_details, dict):
                    existing_details = {}
                existing_details.update(detail_payload)
                stage_payload["details"] = existing_details
            else:
                existing_details = stage_payload.get("details")
                stage_payload["details"] = dict(existing_details) if isinstance(existing_details, dict) else {}

            if next_status == "running":
                stage_payload["started_at"] = now
                stage_payload["finished_at"] = ""
                snapshot["current_stage"] = stage_name
                if not str(snapshot.get("created_at") or "").strip():
                    snapshot["created_at"] = now
            elif next_status in self.STAGE_TERMINAL:
                if not str(stage_payload.get("started_at") or "").strip():
                    stage_payload["started_at"] = now
                stage_payload["finished_at"] = now
                if str(snapshot.get("current_stage") or "") == stage_name:
                    snapshot["current_stage"] = ""

            clean_error = str(error or "").strip()
            if clean_error:
                stage_payload["error"] = clean_error
            elif next_status in {"completed", "skipped", "pending"}:
                stage_payload["error"] = ""

            snapshot["last_event"] = str(event or f"{stage_name}:{next_status}")
            snapshot["updated_at"] = now
            snapshot["overall_status"] = self._derive_overall_status(snapshot)

            self._write_snapshot_locked(conn, snapshot)
            conn.commit()
        return snapshot

    def get_video_snapshot(self, case_id: str, filename: str) -> dict[str, Any] | None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        with self._lock, self._managed_connection() as conn:
            row = conn.execute(
                """
                SELECT snapshot_json
                FROM video_pipeline_latest
                WHERE case_id = ? AND filename = ?
                """,
                (normalized_case_id, normalized_filename),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row["snapshot_json"]))
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return None
        return self._coerce_snapshot(normalized_case_id, normalized_filename, payload)

    def list_case_snapshots(self, case_id: str) -> list[dict[str, Any]]:
        normalized_case_id = self._normalize_case_id(case_id)
        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(
                """
                SELECT filename, snapshot_json
                FROM video_pipeline_latest
                WHERE case_id = ?
                ORDER BY updated_at DESC, filename ASC
                """,
                (normalized_case_id,),
            ).fetchall()

        output: list[dict[str, Any]] = []
        for row in rows:
            filename = str(row["filename"] or "").strip()
            if not filename:
                continue
            try:
                payload = json.loads(str(row["snapshot_json"]))
            except Exception:
                payload = None
            if not isinstance(payload, dict):
                continue
            output.append(self._coerce_snapshot(normalized_case_id, filename, payload))
        return output

    def delete_video(self, case_id: str, filename: str) -> None:
        normalized_case_id = self._normalize_case_id(case_id)
        normalized_filename = self._normalize_filename(filename)
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                DELETE FROM video_pipeline_latest
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
                DELETE FROM video_pipeline_latest
                WHERE case_id = ?
                """,
                (normalized_case_id,),
            )
            conn.commit()

    def mark_running_as_interrupted(self) -> int:
        changed_count = 0
        now = self._utc_now_iso()

        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(
                """
                SELECT case_id, filename, snapshot_json
                FROM video_pipeline_latest
                """
            ).fetchall()
            for row in rows:
                case_id = str(row["case_id"] or "").strip()
                filename = str(row["filename"] or "").strip()
                if not case_id or not filename:
                    continue
                try:
                    payload = json.loads(str(row["snapshot_json"]))
                except Exception:
                    payload = None

                snapshot = self._coerce_snapshot(case_id, filename, payload if isinstance(payload, dict) else None)
                stages = snapshot.get("stages", {})
                if not isinstance(stages, dict):
                    continue

                changed_snapshot = False
                for stage_name in self.STAGES:
                    stage = stages.get(stage_name)
                    if not isinstance(stage, dict):
                        continue
                    if str(stage.get("status") or "") != "running":
                        continue
                    stage["status"] = "interrupted"
                    stage["updated_at"] = now
                    stage["finished_at"] = now
                    stage["error"] = "Interrupted during application restart."
                    changed_snapshot = True

                if not changed_snapshot:
                    continue

                snapshot["current_stage"] = ""
                snapshot["updated_at"] = now
                snapshot["last_event"] = "startup_interrupted_running_stage"
                snapshot["overall_status"] = self._derive_overall_status(snapshot)
                self._write_snapshot_locked(conn, snapshot)
                changed_count += 1

            conn.commit()

        return changed_count

