from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from backend.video_processing import iter_video_frames

PERSON_CLASS_ID = 0
VEHICLE_CLASS_IDS = {1, 2, 3, 5, 7}


@dataclass(frozen=True)
class AnalysisSelection:
    face_people: bool = False
    vehicles: bool = False

    def any_selected(self) -> bool:
        return self.face_people or self.vehicles

    def requires_yolo(self) -> bool:
        return self.face_people or self.vehicles

    def to_dict(self) -> dict[str, bool]:
        return {
            "face_people": bool(self.face_people),
            "vehicles": bool(self.vehicles),
        }


class VideoAnalyzer:
    def __init__(
        self,
        model_path: str | None = None,
        confidence: float = 0.3,
        iou: float = 0.45,
    ) -> None:
        self.confidence = max(0.05, min(0.95, float(confidence)))
        self.iou = max(0.05, min(0.95, float(iou)))
        self.model = None
        self.model_source = ""
        self.error_message = ""
        self._yolo_import_error = ""

        face_cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self.face_detector = cv2.CascadeClassifier(str(face_cascade_path))
        if self.face_detector.empty():
            self.face_detector = None

        try:
            from ultralytics import YOLO  # type: ignore

            resolved_path = self._resolve_model_path(model_path)
            self.model = YOLO(resolved_path)
            self.model_source = str(resolved_path)
        except Exception as exc:
            self.error_message = str(exc)
            if "No module named" in self.error_message and "ultralytics" in self.error_message:
                self._yolo_import_error = (
                    "ultralytics is not installed. Install dependencies from requirements.txt."
                )

    def _resolve_model_path(self, requested_path: str | None) -> str:
        if requested_path and str(requested_path).strip():
            return str(requested_path).strip()

        from_env = os.getenv("YOLO_MODEL_PATH", "").strip()
        if from_env:
            return from_env

        local_default = Path(__file__).resolve().parent.parent / "models" / "yolov8s.pt"
        if local_default.exists():
            return str(local_default)

        # Fallback to a known Ultralytics model name.
        return "yolov8s.pt"

    @property
    def available(self) -> bool:
        return self.model is not None

    def detector_label(self) -> str:
        if self.available:
            return f"yolo({self.model_source})+haar(face)"
        if self._yolo_import_error:
            return self._yolo_import_error
        if self.error_message:
            return f"analysis unavailable: {self.error_message}"
        return "analysis unavailable"

    def _count_faces(self, frame_rgb: np.ndarray) -> int:
        return len(self.detect_faces(frame_rgb))

    def detect_faces(self, frame_rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
        if self.face_detector is None:
            return []
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        faces = self.face_detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(24, 24),
        )
        results: list[tuple[int, int, int, int]] = []
        for x, y, w, h in faces:
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = max(x1 + 1, int(x + w))
            y2 = max(y1 + 1, int(y + h))
            results.append((x1, y1, x2, y2))
        return results

    def _predict_people_and_vehicles(
        self,
        frame_rgb: np.ndarray,
    ) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
        if self.model is None:
            raise RuntimeError(self.detector_label())

        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        results = self.model.predict(
            source=frame_bgr,
            conf=self.confidence,
            iou=self.iou,
            verbose=False,
        )
        if not results:
            return [], []

        boxes = results[0].boxes
        if boxes is None or boxes.cls is None:
            return [], []

        xyxy = boxes.xyxy.detach().cpu().numpy()
        class_ids = boxes.cls.detach().cpu().numpy().astype(np.int32).tolist()
        people_boxes: list[tuple[int, int, int, int]] = []
        vehicle_boxes: list[tuple[int, int, int, int]] = []

        for idx, class_id in enumerate(class_ids):
            x1, y1, x2, y2 = xyxy[idx].tolist()
            box = (
                max(0, int(round(x1))),
                max(0, int(round(y1))),
                max(1, int(round(x2))),
                max(1, int(round(y2))),
            )
            if class_id == PERSON_CLASS_ID:
                people_boxes.append(box)
            elif class_id in VEHICLE_CLASS_IDS:
                vehicle_boxes.append(box)
        return people_boxes, vehicle_boxes

    def detect_frame(
        self,
        frame_rgb: np.ndarray,
        selection: AnalysisSelection,
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        face_boxes: list[tuple[int, int, int, int]] = []
        people_boxes: list[tuple[int, int, int, int]] = []
        vehicle_boxes: list[tuple[int, int, int, int]] = []

        if selection.face_people:
            face_boxes = self.detect_faces(frame_rgb)

        if selection.requires_yolo():
            people_boxes, vehicle_boxes = self._predict_people_and_vehicles(frame_rgb)

        return {
            "faces": face_boxes,
            "people": people_boxes,
            "vehicles": vehicle_boxes,
        }

    def analyze_video(
        self,
        video_path: Path,
        interval_seconds: float,
        selection: AnalysisSelection,
    ) -> dict[str, int | str]:
        if not selection.any_selected():
            return {
                "processed_frames": 0,
                "face_count": 0,
                "people_count": 0,
                "vehicle_count": 0,
                "face_people_hit_frames": 0,
                "vehicle_hit_frames": 0,
                "face_people_first_hit_seconds": -1.0,
                "vehicle_first_hit_seconds": -1.0,
                "detector": self.detector_label(),
            }

        if selection.requires_yolo() and self.model is None:
            raise RuntimeError(self.detector_label())

        processed_frames = 0
        face_count = 0
        people_count = 0
        vehicle_count = 0
        face_people_hit_frames = 0
        vehicle_hit_frames = 0
        face_people_first_hit_seconds = -1.0
        vehicle_first_hit_seconds = -1.0

        for frame in iter_video_frames(video_path, interval_seconds=interval_seconds):
            processed_frames += 1
            detections = self.detect_frame(frame.frame_rgb, selection)
            faces_in_frame = len(detections["faces"])
            people_in_frame = len(detections["people"])
            vehicles_in_frame = len(detections["vehicles"])

            if selection.face_people and (faces_in_frame > 0 or people_in_frame > 0):
                face_people_hit_frames += 1
                if face_people_first_hit_seconds < 0:
                    face_people_first_hit_seconds = float(frame.timestamp_seconds)

            if selection.vehicles and vehicles_in_frame > 0:
                vehicle_hit_frames += 1
                if vehicle_first_hit_seconds < 0:
                    vehicle_first_hit_seconds = float(frame.timestamp_seconds)

            face_count += faces_in_frame
            people_count += people_in_frame
            vehicle_count += vehicles_in_frame

        return {
            "processed_frames": int(processed_frames),
            "face_count": int(face_count),
            "people_count": int(people_count),
            "vehicle_count": int(vehicle_count),
            "face_people_hit_frames": int(face_people_hit_frames),
            "vehicle_hit_frames": int(vehicle_hit_frames),
            "face_people_first_hit_seconds": float(face_people_first_hit_seconds),
            "vehicle_first_hit_seconds": float(vehicle_first_hit_seconds),
            "detector": self.detector_label(),
        }
