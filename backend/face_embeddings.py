from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np
from PIL import Image


class InsightFaceArcEmbedder:
    DEVICE_AUTO = "auto"
    DEVICE_CPU = "cpu"
    DEVICE_CUDA = "cuda"

    def __init__(
        self,
        *,
        model_name: str = "buffalo_l",
        model_root: str | None = None,
        device_preference: str = "auto",
        det_size: int = 640,
    ) -> None:
        self.model_name = str(model_name or "buffalo_l").strip() or "buffalo_l"
        self.model_root = str(model_root or "").strip() or None
        self.device_preference = str(device_preference or "auto").strip().lower() or self.DEVICE_AUTO
        self.det_size = max(320, int(det_size))

        self.available = False
        self.error_message = ""
        self.device = self.DEVICE_CPU
        self.providers: list[str] = []
        self.embedding_dim = 512
        self._analysis = None

        self._initialize()

    @staticmethod
    def _normalize_embedding(vector: np.ndarray) -> np.ndarray:
        array = np.asarray(vector, dtype=np.float32).reshape(-1)
        if array.size == 0:
            return array
        norm = float(np.linalg.norm(array))
        if norm <= 1e-12:
            return array
        return (array / norm).astype(np.float32)

    def _provider_attempts(self) -> list[tuple[list[str], int, str]]:
        preference = self.device_preference
        if preference in {"gpu", self.DEVICE_CUDA}:
            return [
                (["CUDAExecutionProvider", "CPUExecutionProvider"], 0, self.DEVICE_CUDA),
                (["CPUExecutionProvider"], -1, self.DEVICE_CPU),
            ]
        if preference == self.DEVICE_CPU:
            return [(["CPUExecutionProvider"], -1, self.DEVICE_CPU)]
        return [
            (["CUDAExecutionProvider", "CPUExecutionProvider"], 0, self.DEVICE_CUDA),
            (["CPUExecutionProvider"], -1, self.DEVICE_CPU),
        ]

    def _initialize(self) -> None:
        try:
            from insightface.app import FaceAnalysis  # type: ignore
        except Exception as exc:
            self.error_message = (
                "insightface is not installed. Install insightface + onnxruntime to enable FACE-02."
            )
            self.available = False
            if str(exc):
                self.error_message += f" ({exc})"
            return

        last_error = ""
        for providers, ctx_id, device_label in self._provider_attempts():
            try:
                analysis = FaceAnalysis(
                    name=self.model_name,
                    root=self.model_root,
                    providers=providers,
                    allowed_modules=["detection", "recognition"],
                )
                analysis.prepare(ctx_id=ctx_id, det_size=(self.det_size, self.det_size))
                self._analysis = analysis
                self.providers = list(providers)
                self.device = device_label
                self.available = True
                self.error_message = ""
                return
            except Exception as exc:
                last_error = str(exc)

        self.available = False
        self.error_message = last_error or "Unable to initialize InsightFace."

    def engine_label(self) -> str:
        if self.available:
            providers = ",".join(self.providers) if self.providers else "unknown"
            return f"insightface({self.model_name}) device={self.device} providers={providers}"
        if self.error_message:
            return f"insightface unavailable: {self.error_message}"
        return "insightface unavailable"

    @staticmethod
    def _largest_face(
        candidates: list[tuple[np.ndarray, tuple[int, int, int, int]]],
    ) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
        if not candidates:
            return None
        best = None
        best_area = -1
        for embedding, box in candidates:
            x1, y1, x2, y2 = box
            area = max(0, x2 - x1) * max(0, y2 - y1)
            if area > best_area:
                best_area = area
                best = (embedding, box)
        return best

    def encode_probe_face(
        self,
        image: Image.Image,
    ) -> tuple[np.ndarray | None, tuple[int, int, int, int] | None]:
        if not self.available or self._analysis is None:
            return None, None

        frame_rgb = np.asarray(image.convert("RGB"))
        if frame_rgb.size == 0:
            return None, None

        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        try:
            detections = self._analysis.get(frame_bgr)
        except Exception:
            return None, None
        if not detections:
            return None, None

        candidates: list[tuple[np.ndarray, tuple[int, int, int, int]]] = []
        for detected in detections:
            raw_box = getattr(detected, "bbox", None)
            if raw_box is None or len(raw_box) < 4:
                continue
            x1, y1, x2, y2 = [int(round(float(value))) for value in raw_box[:4]]
            if x2 <= x1 or y2 <= y1:
                continue
            raw_embedding = getattr(detected, "normed_embedding", None)
            if raw_embedding is None:
                raw_embedding = getattr(detected, "embedding", None)
            if raw_embedding is None:
                continue
            embedding = self._normalize_embedding(np.asarray(raw_embedding, dtype=np.float32))
            if embedding.size == 0:
                continue
            self.embedding_dim = int(embedding.shape[0])
            candidates.append((embedding, (x1, y1, x2, y2)))

        selected = self._largest_face(candidates)
        if selected is None:
            return None, None
        return selected

    def encode_face_crops(
        self,
        images: Sequence[Image.Image],
    ) -> tuple[np.ndarray, list[int]]:
        if not images:
            return np.empty((0, self.embedding_dim), dtype=np.float32), []

        vectors: list[np.ndarray] = []
        matched_indices: list[int] = []
        for index, image in enumerate(images):
            embedding, _ = self.encode_probe_face(image)
            if embedding is None:
                continue
            vectors.append(embedding)
            matched_indices.append(index)

        if not vectors:
            return np.empty((0, self.embedding_dim), dtype=np.float32), []

        stacked = np.vstack(vectors).astype(np.float32, copy=False)
        return stacked, matched_indices
