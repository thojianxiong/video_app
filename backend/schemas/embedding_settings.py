from __future__ import annotations

from pydantic import BaseModel, Field


class EmbeddingSettingsUpdateRequest(BaseModel):
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    pretrained: str | None = Field(default=None, min_length=1, max_length=160)
    device_preference: str | None = Field(default=None, min_length=1, max_length=16)

