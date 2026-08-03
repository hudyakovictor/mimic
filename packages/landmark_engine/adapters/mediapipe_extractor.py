"""MediaPipe adapter for the framework-independent landmark engine."""

from __future__ import annotations

import os
import tempfile
from typing import BinaryIO

from ..domain import HeadPose, LandmarkFrame, LandmarkSequence, Point3D


class MediaPipeLandmarkExtractor:
    """Extract a single face track while preserving decoder timestamps.

    MediaPipe is an optional dependency. The adapter deliberately emits gaps as
    confidence-zero frames; interpolation belongs to the quality policy, not extraction.
    """

    def __init__(self, *, min_confidence: float = 0.5, max_faces: int = 1) -> None:
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be in [0, 1]")
        if max_faces != 1:
            raise ValueError("MimicGuard v1 supports exactly one claimed face track")
        self.min_confidence = min_confidence

    def extract(self, video: BinaryIO, *, track_id: str) -> LandmarkSequence:
        import cv2
        import mediapipe as mp

        if not track_id.strip():
            raise ValueError("track_id is required")
        suffix = os.path.splitext(getattr(video, "name", "video.mp4"))[1] or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            while chunk := video.read(1024 * 1024):
                tmp.write(chunk)
            tmp.flush()
            capture = cv2.VideoCapture(tmp.name)
            if not capture.isOpened():
                raise ValueError("Unable to decode video")
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0) or 30.0
            frames: list[LandmarkFrame] = []
            try:
                with mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=self.min_confidence,
                    min_tracking_confidence=self.min_confidence,
                ) as mesh:
                    frame_index = 0
                    while True:
                        ok, bgr = capture.read()
                        if not ok:
                            break
                        timestamp = capture.get(cv2.CAP_PROP_POS_MSEC)
                        timestamp_ms = int(timestamp if timestamp > 0 else frame_index * 1000 / fps)
                        result = mesh.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                        points: dict[int, Point3D] = {}
                        confidence = 0.0
                        if result.multi_face_landmarks:
                            face = result.multi_face_landmarks[0]
                            points = {
                                index: Point3D(float(point.x), float(point.y), float(point.z))
                                for index, point in enumerate(face.landmark)
                            }
                            confidence = 1.0
                        frames.append(
                            LandmarkFrame(timestamp_ms, points, confidence, HeadPose(0.0, 0.0, 0.0))
                        )
                        frame_index += 1
            finally:
                capture.release()
        return LandmarkSequence(track_id, "mediapipe-478-v1", tuple(frames), fps)
