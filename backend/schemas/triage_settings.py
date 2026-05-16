from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TriageSettingsUpdateRequest(BaseModel):
    checkpoint_mode: Literal["mountain", "peaks", "change_point", "anomaly", "balanced"] | None = None
