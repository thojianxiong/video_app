from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


@dataclass(frozen=True)
class CasePaths:
    case_id: str
    case_dir: Path
    videos_dir: Path
    thumbnails_dir: Path
    data_dir: Path
    index_path: Path
    metadata_path: Path
    temporal_index_path: Path
    temporal_metadata_path: Path
    face_people_index_path: Path
    face_people_metadata_path: Path
    face_identity_index_path: Path
    face_identity_metadata_path: Path
    vehicles_index_path: Path
    vehicles_metadata_path: Path


def normalize_case_id(case_id: str) -> str:
    raw = str(case_id or "").strip()
    if not raw:
        raise ValueError("case_id is required")
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in raw)
    if not safe:
        raise ValueError("Invalid case_id")
    return safe


def build_case_paths(case_id: str, *, cases_dir: Path) -> CasePaths:
    normalized = normalize_case_id(case_id)
    case_dir = cases_dir / normalized
    videos_dir = case_dir / "videos"
    thumbnails_dir = case_dir / "thumbnails"
    data_dir = case_dir / "data"
    return CasePaths(
        case_id=normalized,
        case_dir=case_dir,
        videos_dir=videos_dir,
        thumbnails_dir=thumbnails_dir,
        data_dir=data_dir,
        index_path=data_dir / "faiss.index",
        metadata_path=data_dir / "metadata.json",
        temporal_index_path=data_dir / "temporal_faiss.index",
        temporal_metadata_path=data_dir / "temporal_metadata.json",
        face_people_index_path=data_dir / "face_people.index",
        face_people_metadata_path=data_dir / "face_people_metadata.json",
        face_identity_index_path=data_dir / "face_identity.index",
        face_identity_metadata_path=data_dir / "face_identity_metadata.json",
        vehicles_index_path=data_dir / "vehicles.index",
        vehicles_metadata_path=data_dir / "vehicles_metadata.json",
    )


def ensure_case_directories(case_paths: CasePaths) -> None:
    for path in (
        case_paths.case_dir,
        case_paths.videos_dir,
        case_paths.thumbnails_dir,
        case_paths.data_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def empty_cases_registry() -> dict:
    return {"next_numeric_id": 1, "cases": []}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_case_created_at(case_id: str, *, cases_dir: Path) -> str:
    case_dir = cases_dir / case_id
    if case_dir.exists() and case_dir.is_dir():
        try:
            created_at_ts = case_dir.stat().st_ctime
            return datetime.fromtimestamp(created_at_ts, timezone.utc).isoformat()
        except Exception:
            return utc_now_iso()
    return utc_now_iso()


def load_cases_registry_locked(
    *,
    cases_registry_path: Path,
    cases_dir: Path,
) -> dict:
    if not cases_registry_path.exists():
        return empty_cases_registry()

    try:
        payload = json.loads(cases_registry_path.read_text(encoding="utf-8"))
    except Exception:
        return empty_cases_registry()

    if not isinstance(payload, dict):
        return empty_cases_registry()

    raw_cases = payload.get("cases", [])
    if not isinstance(raw_cases, list):
        raw_cases = []

    cleaned_cases: list[dict[str, str]] = []
    changed = False
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        case_id_raw = item.get("case_id")
        name_raw = item.get("name")
        if case_id_raw is None or name_raw is None:
            continue
        try:
            cleaned_case_id = normalize_case_id(str(case_id_raw))
        except ValueError:
            continue
        cleaned_name = str(name_raw).strip() or cleaned_case_id
        created_at_raw = item.get("created_at")
        cleaned_created_at = (
            str(created_at_raw).strip()
            if isinstance(created_at_raw, str) and str(created_at_raw).strip()
            else ""
        )
        if not cleaned_created_at:
            cleaned_created_at = infer_case_created_at(cleaned_case_id, cases_dir=cases_dir)
            changed = True
        cleaned_cases.append(
            {
                "case_id": cleaned_case_id,
                "name": cleaned_name,
                "created_at": cleaned_created_at,
            }
        )

    next_numeric_id = payload.get("next_numeric_id", 1)
    try:
        next_numeric_id = int(next_numeric_id)
    except Exception:
        next_numeric_id = 1
    next_numeric_id = max(1, next_numeric_id)

    if changed:
        payload["next_numeric_id"] = next_numeric_id
        payload["cases"] = cleaned_cases
        save_cases_registry_locked(
            payload,
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )

    return {"next_numeric_id": next_numeric_id, "cases": cleaned_cases}


def save_cases_registry_locked(
    payload: dict,
    *,
    cases_registry_path: Path,
    cases_dir: Path,
) -> None:
    cases_dir.mkdir(parents=True, exist_ok=True)
    cases_registry_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def find_case_locked(payload: dict, case_id: str) -> dict | None:
    for item in payload.get("cases", []):
        if item.get("case_id") == case_id:
            return item
    return None


def list_cases_sync(
    *,
    cases_registry_path: Path,
    cases_dir: Path,
    case_registry_lock: Lock,
) -> list[dict[str, str]]:
    with case_registry_lock:
        payload = load_cases_registry_locked(
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )
        cases = sorted(
            payload["cases"],
            key=lambda item: (
                str(item.get("created_at", "")),
                str(item.get("case_id", "")),
            ),
        )

    for item in cases:
        ensure_case_directories(
            build_case_paths(item["case_id"], cases_dir=cases_dir),
        )

    return [
        {
            "case_id": item["case_id"],
            "name": item["name"],
            "created_at": str(item.get("created_at", "")),
        }
        for item in cases
    ]


def create_case_sync(
    name: str,
    *,
    cases_registry_path: Path,
    cases_dir: Path,
    case_registry_lock: Lock,
) -> dict[str, str]:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("Case name cannot be empty")

    with case_registry_lock:
        payload = load_cases_registry_locked(
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )
        existing_ids = {
            str(item.get("case_id"))
            for item in payload.get("cases", [])
            if item.get("case_id")
        }

        case_id = str(uuid4())
        while case_id in existing_ids:
            case_id = str(uuid4())

        created_at = utc_now_iso()
        payload["cases"].append(
            {
                "case_id": case_id,
                "name": clean_name,
                "created_at": created_at,
            }
        )
        save_cases_registry_locked(
            payload,
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )

    ensure_case_directories(build_case_paths(case_id, cases_dir=cases_dir))
    return {"case_id": case_id, "name": clean_name, "created_at": created_at}


def delete_case_sync(
    case_id: str,
    *,
    cases_registry_path: Path,
    cases_dir: Path,
    case_registry_lock: Lock,
) -> dict[str, str]:
    normalized = normalize_case_id(case_id)

    with case_registry_lock:
        payload = load_cases_registry_locked(
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )
        deleted_case = find_case_locked(payload, normalized)
        if deleted_case is None:
            raise KeyError(normalized)
        deleted_case = {
            "case_id": str(deleted_case.get("case_id") or normalized),
            "name": str(deleted_case.get("name") or normalized),
            "created_at": str(deleted_case.get("created_at") or ""),
        }

    case_paths = build_case_paths(normalized, cases_dir=cases_dir)
    if case_paths.case_dir.exists():
        shutil.rmtree(case_paths.case_dir)

    with case_registry_lock:
        payload = load_cases_registry_locked(
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )
        existing_cases = payload.get("cases", [])
        remaining_cases: list[dict[str, str]] = []
        for item in existing_cases:
            if item.get("case_id") == normalized:
                continue
            remaining_cases.append(item)
        payload["cases"] = remaining_cases
        save_cases_registry_locked(
            payload,
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )

    deleted_name = str(deleted_case.get("name") or normalized)
    deleted_created_at = str(deleted_case.get("created_at") or "")
    return {
        "case_id": normalized,
        "name": deleted_name,
        "created_at": deleted_created_at,
    }


def rename_case_sync(
    case_id: str,
    name: str,
    *,
    cases_registry_path: Path,
    cases_dir: Path,
    case_registry_lock: Lock,
) -> dict[str, str]:
    normalized = normalize_case_id(case_id)
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValueError("Case name cannot be empty")

    with case_registry_lock:
        payload = load_cases_registry_locked(
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )
        case = find_case_locked(payload, normalized)
        if case is None:
            raise KeyError(normalized)
        case["name"] = clean_name
        save_cases_registry_locked(
            payload,
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )

    return {
        "case_id": normalized,
        "name": clean_name,
        "created_at": str(case.get("created_at") or ""),
    }


def get_case_paths_or_raise(
    case_id: str,
    *,
    cases_registry_path: Path,
    cases_dir: Path,
    case_registry_lock: Lock,
) -> CasePaths:
    normalized = normalize_case_id(case_id)
    with case_registry_lock:
        payload = load_cases_registry_locked(
            cases_registry_path=cases_registry_path,
            cases_dir=cases_dir,
        )
        case = find_case_locked(payload, normalized)
    if case is None:
        raise KeyError(normalized)

    case_paths = build_case_paths(normalized, cases_dir=cases_dir)
    ensure_case_directories(case_paths)
    return case_paths


def resolve_case_id_or_default(
    case_id: str | None,
    *,
    cases_registry_path: Path,
    cases_dir: Path,
    case_registry_lock: Lock,
) -> str:
    if case_id and str(case_id).strip():
        return normalize_case_id(case_id)

    cases = list_cases_sync(
        cases_registry_path=cases_registry_path,
        cases_dir=cases_dir,
        case_registry_lock=case_registry_lock,
    )
    if cases:
        return normalize_case_id(cases[0]["case_id"])

    raise ValueError("No cases available. Create a case first.")
