from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class IndexJobStore:
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
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _ensure_db(self) -> None:
        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS index_jobs_latest (
                    case_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    running INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT '',
                    snapshot_json TEXT NOT NULL
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
    def _coerce_snapshot(case_id: str, snapshot: dict | None) -> dict:
        payload = dict(snapshot or {})
        payload["case_id"] = case_id
        payload.setdefault("status", "idle")
        payload.setdefault("running", False)
        payload.setdefault("updated_at", "")
        return payload

    def upsert_snapshot(self, snapshot: dict) -> None:
        case_id = self._normalize_case_id(str(snapshot.get("case_id") or ""))
        payload = self._coerce_snapshot(case_id, snapshot)
        status = str(payload.get("status") or "idle")
        running = 1 if bool(payload.get("running")) else 0
        updated_at = str(payload.get("updated_at") or "")
        encoded = json.dumps(payload, ensure_ascii=True)

        with self._lock, self._managed_connection() as conn:
            conn.execute(
                """
                INSERT INTO index_jobs_latest(case_id, status, running, updated_at, snapshot_json)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    status=excluded.status,
                    running=excluded.running,
                    updated_at=excluded.updated_at,
                    snapshot_json=excluded.snapshot_json
                """,
                (case_id, status, running, updated_at, encoded),
            )
            conn.commit()

    def delete_case(self, case_id: str) -> None:
        normalized = self._normalize_case_id(case_id)
        with self._lock, self._managed_connection() as conn:
            conn.execute("DELETE FROM index_jobs_latest WHERE case_id = ?", (normalized,))
            conn.commit()

    def get_case_snapshot(self, case_id: str) -> dict | None:
        normalized = self._normalize_case_id(case_id)
        with self._lock, self._managed_connection() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM index_jobs_latest WHERE case_id = ?",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row["snapshot_json"]))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        payload["case_id"] = normalized
        return payload

    def load_all_snapshots(self) -> dict[str, dict]:
        output: dict[str, dict] = {}
        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(
                "SELECT case_id, snapshot_json FROM index_jobs_latest"
            ).fetchall()
        for row in rows:
            case_id = str(row["case_id"] or "").strip()
            if not case_id:
                continue
            try:
                payload = json.loads(str(row["snapshot_json"]))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            payload["case_id"] = case_id
            output[case_id] = payload
        return output

    def mark_incomplete_jobs_interrupted(self) -> int:
        now = self._utc_now_iso()
        changed = 0

        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(
                """
                SELECT case_id, snapshot_json, status, running
                FROM index_jobs_latest
                """
            ).fetchall()

            for row in rows:
                case_id = str(row["case_id"] or "").strip()
                if not case_id:
                    continue
                status = str(row["status"] or "")
                running = bool(int(row["running"] or 0))
                if not running and status not in {"queued", "running", "cancelling"}:
                    continue

                try:
                    payload = json.loads(str(row["snapshot_json"]))
                except Exception:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}

                payload["case_id"] = case_id
                payload["status"] = "interrupted"
                payload["running"] = False
                payload["cancel_requested"] = True
                payload["updated_at"] = now
                if not str(payload.get("finished_at") or "").strip():
                    payload["finished_at"] = now
                errors = payload.get("errors")
                if not isinstance(errors, list):
                    errors = []
                    payload["errors"] = errors
                note = "Marked interrupted on startup."
                if note not in errors:
                    errors.append(note)

                conn.execute(
                    """
                    UPDATE index_jobs_latest
                    SET status = ?, running = ?, updated_at = ?, snapshot_json = ?
                    WHERE case_id = ?
                    """,
                    (
                        "interrupted",
                        0,
                        now,
                        json.dumps(payload, ensure_ascii=True),
                        case_id,
                    ),
                )
                changed += 1

            conn.commit()

        return changed
