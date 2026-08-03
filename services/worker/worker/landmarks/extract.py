"""MediaPipe Face Mesh extraction.

MG-STUB: final — production implementation.
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)
MODEL_DIR = os.path.expanduser("~/.cache/mimicguard")


def _ensure_model() -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, "face_landmarker.task")
    if not os.path.exists(path):
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


@dataclass
class FaceFrame:
    timestamp_ms: int
    points_2d: np.ndarray  # (478, 3) x,y,z normalized
    confidence: float
    yaw: float
    pitch: float
    roll: float


def extract_landmarks_from_frames(
    frames_bgr: Iterable[np.ndarray],
    fps: float,
    min_confidence: float = 0.5,
) -> list[FaceFrame]:
    """Run MediaPipe Face Landmarker on a list of BGR frames.

    Returns: list of FaceFrame (one per frame, even when detection fails — confidence=0).
    """
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    model_path = _ensure_model()
    base = mp_python.BaseOptions(model_asset_path=model_path)
    options = mp_vision.FaceLandmarkerOptions(
        base_options=base,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=min_confidence,
        min_face_presence_confidence=min_confidence,
        min_tracking_confidence=min_confidence,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
    )
    landmarker = mp_vision.FaceLandmarker.create_from_options(options)

    out: list[FaceFrame] = []
    for i, bgr in enumerate(frames_bgr):
        ts_ms = int(i * 1000 / max(1e-3, fps))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        try:
            result = landmarker.detect_for_video(mp_image, ts_ms)
        except Exception:
            out.append(FaceFrame(ts_ms, np.zeros((478, 3), dtype=np.float32), 0.0, 0, 0, 0))
            continue
        if not result.face_landmarks:
            out.append(FaceFrame(ts_ms, np.zeros((478, 3), dtype=np.float32), 0.0, 0, 0, 0))
            continue
        lm = result.face_landmarks[0]
        pts = np.array([[p.x, p.y, p.z] for p in lm], dtype=np.float32)
        yaw, pitch, roll = 0.0, 0.0, 0.0
        if result.facial_transformation_matrixes:
            yaw, pitch, roll = _decompose_pose(result.facial_transformation_matrixes[0])
        out.append(FaceFrame(ts_ms, pts, 1.0, yaw, pitch, roll))
    return out


def _decompose_pose(matrix) -> tuple[float, float, float]:
    """Convert 4x4 transformation matrix to yaw/pitch/roll (degrees)."""
    m = np.asarray(matrix).reshape(4, 4)
    r = m[:3, :3]
    sy = float(np.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2))
    singular = sy < 1e-6
    if not singular:
        pitch = np.degrees(np.arctan2(r[2, 1], r[2, 2]))
        yaw = np.degrees(np.arctan2(-r[2, 0], sy))
        roll = np.degrees(np.arctan2(r[1, 0], r[0, 0]))
    else:
        pitch = np.degrees(np.arctan2(-r[1, 2], r[1, 1]))
        yaw = np.degrees(np.arctan2(-r[2, 0], sy))
        roll = 0.0
    return float(yaw), float(pitch), float(roll)


def write_landmarks_npz(frames: list[FaceFrame], path: str, fps: float = 30.0) -> None:
    """Write a compact binary landmarks file: header JSON + raw float32 array.

    Format:
        line 1: JSON header {"shape": [T, 478, 3], "dtype": "float32", "schema": "mediapipe-v1", "fps": 30.0}
        line 2+: binary float32 array shape (T, 478, 3) for landmarks_3d
        then binary float32 shape (T, 4) for [ts_ms, conf, yaw, pitch] (or roll dropped)
    """
    import json

    if not frames:
        raise ValueError("No frames to write")
    arr = np.stack([f.points_2d for f in frames], axis=0).astype(np.float32)
    meta = np.zeros((len(frames), 4), dtype=np.float32)
    for i, f in enumerate(frames):
        meta[i, 0] = f.timestamp_ms
        meta[i, 1] = f.confidence
        meta[i, 2] = f.yaw
        meta[i, 3] = f.pitch  # roll dropped to keep 4-dim meta
    header = json.dumps(
        {
            "shape": list(arr.shape),
            "dtype": "float32",
            "schema": "mediapipe-v1",
            "fps": float(fps),
            "meta_shape": list(meta.shape),
        }
    ).encode()
    with open(path, "wb") as output:
        output.write(header + b"\n")
        output.write(arr.tobytes())
        output.write(meta.tobytes())


def normalize_landmarks(frames: list[FaceFrame]) -> np.ndarray:
    """Apply translation (subtract nose_tip) and scale (divide by eye distance).

    Returns: np.ndarray shape (T, 33) — 11 motion points x 3 coords.
    """
    if not frames:
        return np.zeros((0, 33), dtype=np.float32)
    nose_tip = 1
    left_eye_outer = 33
    right_eye_outer = 263
    motion_indices = (61, 291, 13, 14, 78, 308, 152, 234, 454, 50, 280)
    out = np.zeros((len(frames), 33), dtype=np.float32)
    for i, fr in enumerate(frames):
        if fr.confidence < 0.5 or fr.points_2d[nose_tip].sum() == 0:
            continue
        nose = fr.points_2d[nose_tip]
        le = fr.points_2d[left_eye_outer]
        re = fr.points_2d[right_eye_outer]
        scale = float(np.linalg.norm(re[:2] - le[:2]))
        if scale <= 1e-8:
            continue
        for j, idx in enumerate(motion_indices):
            p = fr.points_2d[idx]
            out[i, j * 3 : j * 3 + 3] = (p - nose) / scale
    return out
