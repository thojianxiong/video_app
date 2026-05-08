from __future__ import annotations

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from backend.schemas.embedding_settings import EmbeddingSettingsUpdateRequest
from backend.schemas.search_settings import SearchSettingsUpdateRequest


def build_embedding_settings_router(
    *,
    read_saved_settings_sync: Callable[[], dict[str, str]],
    write_saved_settings_sync: Callable[..., dict[str, str]],
    build_settings_response_sync: Callable[[], dict],
    read_saved_search_settings_sync: Callable[[], dict],
    write_saved_search_settings_sync: Callable[..., dict],
    build_search_settings_response_sync: Callable[[], dict],
) -> APIRouter:
    router = APIRouter(tags=["settings"])

    @router.get("/settings/embedding")
    async def get_embedding_settings() -> dict:
        try:
            return await asyncio.to_thread(build_settings_response_sync)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/settings/embedding")
    async def update_embedding_settings(request: EmbeddingSettingsUpdateRequest) -> dict:
        try:
            saved = await asyncio.to_thread(read_saved_settings_sync)
            model_name = (
                request.model_name.strip()
                if isinstance(request.model_name, str)
                else saved["model_name"]
            )
            pretrained = (
                request.pretrained.strip()
                if isinstance(request.pretrained, str)
                else saved["pretrained"]
            )
            device_preference = (
                request.device_preference.strip()
                if isinstance(request.device_preference, str)
                else saved["device_preference"]
            )
            await asyncio.to_thread(
                write_saved_settings_sync,
                model_name=model_name,
                pretrained=pretrained,
                device_preference=device_preference,
            )
            return await asyncio.to_thread(build_settings_response_sync)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/settings/search")
    async def get_search_settings() -> dict:
        try:
            return await asyncio.to_thread(build_search_settings_response_sync)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/settings/search")
    async def update_search_settings(request: SearchSettingsUpdateRequest) -> dict:
        try:
            saved = await asyncio.to_thread(read_saved_search_settings_sync)
            score_threshold = (
                float(request.score_threshold)
                if request.score_threshold is not None
                else float(saved.get("score_threshold", 0.22))
            )
            dedupe_aggressiveness = (
                float(request.dedupe_aggressiveness)
                if request.dedupe_aggressiveness is not None
                else float(saved.get("dedupe_aggressiveness", 55.0))
            )
            result_limit = (
                int(request.result_limit)
                if request.result_limit is not None
                else int(saved.get("result_limit", 120))
            )
            await asyncio.to_thread(
                write_saved_search_settings_sync,
                score_threshold=score_threshold,
                dedupe_aggressiveness=dedupe_aggressiveness,
                result_limit=result_limit,
            )
            return await asyncio.to_thread(build_search_settings_response_sync)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return router
