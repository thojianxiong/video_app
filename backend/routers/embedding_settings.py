from __future__ import annotations

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class EmbeddingSettingsUpdateRequest(BaseModel):
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    pretrained: str | None = Field(default=None, min_length=1, max_length=160)
    device_preference: str | None = Field(default=None, min_length=1, max_length=16)


def build_embedding_settings_router(
    *,
    read_saved_settings_sync: Callable[[], dict[str, str]],
    write_saved_settings_sync: Callable[..., dict[str, str]],
    build_settings_response_sync: Callable[[], dict],
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

    return router

