from __future__ import annotations

from pydantic import BaseModel


class AnalysisSettingsUpdateRequest(BaseModel):
    face_identity_enabled: bool | None = None

