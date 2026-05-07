from __future__ import annotations

from pydantic import BaseModel


class ShutdownRequest(BaseModel):
    confirm: bool = False

