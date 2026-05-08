from __future__ import annotations

from pydantic import BaseModel, Field


class SearchSettingsUpdateRequest(BaseModel):
    score_threshold: float | None = Field(default=None, ge=-1.0, le=1.0)
    dedupe_aggressiveness: float | None = Field(default=None, ge=0.0, le=100.0)
    result_limit: int | None = Field(default=None, ge=10, le=500)
