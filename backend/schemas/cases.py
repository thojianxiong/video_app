from __future__ import annotations

from pydantic import BaseModel, Field


class CaseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class CaseRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)

