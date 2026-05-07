from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

DEFAULT_OPENCLIP_MODEL = "ViT-L-14"
DEFAULT_OPENCLIP_PRETRAINED = "openai"
DEFAULT_OPENCLIP_DEVICE = "auto"

EMBEDDING_MODEL_PROFILES = [
    {
        "id": "balanced_vit_b32_laion2b",
        "label": "Balanced (ViT-B-32 / LAION2B)",
        "model_name": "ViT-B-32",
        "pretrained": "laion2b_s34b_b79k",
    },
    {
        "id": "high_vit_l14_openai",
        "label": "High Accuracy (ViT-L-14 / OpenAI)",
        "model_name": "ViT-L-14",
        "pretrained": "openai",
    },
]

EMBEDDING_DEVICE_OPTIONS = ["auto", "cuda", "cpu"]


def _non_empty_env(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    cleaned = str(raw).strip()
    return cleaned or None


def normalize_device_preference(
    value: str | None,
    *,
    default_device: str = DEFAULT_OPENCLIP_DEVICE,
    device_options: list[str] | tuple[str, ...] = EMBEDDING_DEVICE_OPTIONS,
) -> str:
    normalized = str(value or default_device).strip().lower()
    if normalized not in set(device_options):
        raise ValueError("Invalid device_preference. Allowed values: auto, cuda, cpu.")
    return normalized


def default_embedding_settings(
    *,
    default_model: str = DEFAULT_OPENCLIP_MODEL,
    default_pretrained: str = DEFAULT_OPENCLIP_PRETRAINED,
    default_device: str = DEFAULT_OPENCLIP_DEVICE,
) -> dict[str, str]:
    return {
        "model_name": default_model,
        "pretrained": default_pretrained,
        "device_preference": default_device,
    }


def _load_app_settings_locked(
    *,
    app_settings_path: Path,
    default_embedding: dict[str, str],
) -> dict:
    default_payload = {"embedding": default_embedding}
    if not app_settings_path.exists():
        return default_payload
    try:
        payload = json.loads(app_settings_path.read_text(encoding="utf-8"))
    except Exception:
        return default_payload
    if not isinstance(payload, dict):
        return default_payload
    return payload


def _save_app_settings_locked(*, app_settings_path: Path, payload: dict) -> None:
    app_settings_path.parent.mkdir(parents=True, exist_ok=True)
    app_settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sanitize_embedding_settings(
    raw_embedding: dict | None,
    *,
    default_model: str,
    default_pretrained: str,
    default_device: str,
    device_options: list[str] | tuple[str, ...],
) -> dict[str, str]:
    raw = raw_embedding if isinstance(raw_embedding, dict) else {}
    model_name = str(raw.get("model_name") or default_model).strip()
    pretrained = str(raw.get("pretrained") or default_pretrained).strip()
    try:
        device_preference = normalize_device_preference(
            raw.get("device_preference"),
            default_device=default_device,
            device_options=device_options,
        )
    except ValueError:
        device_preference = default_device

    return {
        "model_name": model_name or default_model,
        "pretrained": pretrained or default_pretrained,
        "device_preference": device_preference,
    }


def read_saved_embedding_settings_sync(
    *,
    app_settings_path: Path,
    app_settings_lock: Lock,
    default_model: str = DEFAULT_OPENCLIP_MODEL,
    default_pretrained: str = DEFAULT_OPENCLIP_PRETRAINED,
    default_device: str = DEFAULT_OPENCLIP_DEVICE,
    device_options: list[str] | tuple[str, ...] = EMBEDDING_DEVICE_OPTIONS,
) -> dict[str, str]:
    with app_settings_lock:
        payload = _load_app_settings_locked(
            app_settings_path=app_settings_path,
            default_embedding=default_embedding_settings(
                default_model=default_model,
                default_pretrained=default_pretrained,
                default_device=default_device,
            ),
        )
        return _sanitize_embedding_settings(
            payload.get("embedding"),
            default_model=default_model,
            default_pretrained=default_pretrained,
            default_device=default_device,
            device_options=device_options,
        )


def write_saved_embedding_settings_sync(
    *,
    app_settings_path: Path,
    app_settings_lock: Lock,
    model_name: str,
    pretrained: str,
    device_preference: str,
    default_model: str = DEFAULT_OPENCLIP_MODEL,
    default_pretrained: str = DEFAULT_OPENCLIP_PRETRAINED,
    default_device: str = DEFAULT_OPENCLIP_DEVICE,
    device_options: list[str] | tuple[str, ...] = EMBEDDING_DEVICE_OPTIONS,
) -> dict[str, str]:
    clean_model = str(model_name or "").strip()
    clean_pretrained = str(pretrained or "").strip()
    clean_device = normalize_device_preference(
        device_preference,
        default_device=default_device,
        device_options=device_options,
    )

    if not clean_model:
        raise ValueError("model_name cannot be empty")
    if not clean_pretrained:
        raise ValueError("pretrained cannot be empty")

    with app_settings_lock:
        payload = _load_app_settings_locked(
            app_settings_path=app_settings_path,
            default_embedding=default_embedding_settings(
                default_model=default_model,
                default_pretrained=default_pretrained,
                default_device=default_device,
            ),
        )
        payload["embedding"] = {
            "model_name": clean_model,
            "pretrained": clean_pretrained,
            "device_preference": clean_device,
        }
        _save_app_settings_locked(app_settings_path=app_settings_path, payload=payload)

    return dict(payload["embedding"])


def embedding_env_overrides() -> dict[str, bool]:
    return {
        "OPENCLIP_MODEL": _non_empty_env("OPENCLIP_MODEL") is not None,
        "OPENCLIP_PRETRAINED": _non_empty_env("OPENCLIP_PRETRAINED") is not None,
        "OPENCLIP_DEVICE": _non_empty_env("OPENCLIP_DEVICE") is not None,
    }


def resolve_effective_embedding_settings_sync(
    *,
    app_settings_path: Path,
    app_settings_lock: Lock,
    saved_settings: dict[str, str] | None = None,
    default_model: str = DEFAULT_OPENCLIP_MODEL,
    default_pretrained: str = DEFAULT_OPENCLIP_PRETRAINED,
    default_device: str = DEFAULT_OPENCLIP_DEVICE,
    device_options: list[str] | tuple[str, ...] = EMBEDDING_DEVICE_OPTIONS,
) -> dict[str, str]:
    saved = saved_settings or read_saved_embedding_settings_sync(
        app_settings_path=app_settings_path,
        app_settings_lock=app_settings_lock,
        default_model=default_model,
        default_pretrained=default_pretrained,
        default_device=default_device,
        device_options=device_options,
    )
    model_name = _non_empty_env("OPENCLIP_MODEL") or saved["model_name"]
    pretrained = _non_empty_env("OPENCLIP_PRETRAINED") or saved["pretrained"]
    env_device = _non_empty_env("OPENCLIP_DEVICE")
    if env_device is None:
        device_pref = saved["device_preference"]
    else:
        device_pref = normalize_device_preference(
            env_device,
            default_device=default_device,
            device_options=device_options,
        )

    return {
        "model_name": str(model_name).strip() or default_model,
        "pretrained": str(pretrained).strip() or default_pretrained,
        "device_preference": device_pref,
    }


def find_embedding_profile_id(
    model_name: str,
    pretrained: str,
    *,
    profiles: list[dict] = EMBEDDING_MODEL_PROFILES,
) -> str | None:
    for profile in profiles:
        if (
            str(profile.get("model_name")) == str(model_name)
            and str(profile.get("pretrained")) == str(pretrained)
        ):
            return str(profile.get("id"))
    return None


def build_embedding_settings_response_sync(
    *,
    app_settings_path: Path,
    app_settings_lock: Lock,
    loaded_embedding: dict[str, str] | None = None,
    profiles: list[dict] = EMBEDDING_MODEL_PROFILES,
    device_options: list[str] | tuple[str, ...] = EMBEDDING_DEVICE_OPTIONS,
    default_model: str = DEFAULT_OPENCLIP_MODEL,
    default_pretrained: str = DEFAULT_OPENCLIP_PRETRAINED,
    default_device: str = DEFAULT_OPENCLIP_DEVICE,
) -> dict:
    saved = read_saved_embedding_settings_sync(
        app_settings_path=app_settings_path,
        app_settings_lock=app_settings_lock,
        default_model=default_model,
        default_pretrained=default_pretrained,
        default_device=default_device,
        device_options=device_options,
    )
    effective = resolve_effective_embedding_settings_sync(
        app_settings_path=app_settings_path,
        app_settings_lock=app_settings_lock,
        saved_settings=saved,
        default_model=default_model,
        default_pretrained=default_pretrained,
        default_device=default_device,
        device_options=device_options,
    )
    env_overrides = embedding_env_overrides()

    loaded_raw = loaded_embedding if isinstance(loaded_embedding, dict) else {}
    loaded = {
        "model_name": str(loaded_raw.get("model_name") or effective["model_name"]),
        "pretrained": str(loaded_raw.get("pretrained") or effective["pretrained"]),
        "device_preference": str(
            loaded_raw.get("device_preference") or effective["device_preference"]
        ),
        "device": str(loaded_raw.get("device") or ""),
    }
    restart_required = (
        loaded["model_name"] != effective["model_name"]
        or loaded["pretrained"] != effective["pretrained"]
        or loaded["device_preference"] != effective["device_preference"]
    )

    profile_payload = [dict(profile) for profile in profiles]
    return {
        "loaded": loaded,
        "saved": saved,
        "effective_next_startup": effective,
        "profiles": profile_payload,
        "device_options": list(device_options),
        "loaded_profile_id": find_embedding_profile_id(
            loaded["model_name"],
            loaded["pretrained"],
            profiles=profiles,
        ),
        "saved_profile_id": find_embedding_profile_id(
            saved["model_name"],
            saved["pretrained"],
            profiles=profiles,
        ),
        "effective_profile_id": find_embedding_profile_id(
            effective["model_name"],
            effective["pretrained"],
            profiles=profiles,
        ),
        "env_overrides": env_overrides,
        "restart_required": restart_required,
        "reindex_required_if_model_changes": True,
    }

