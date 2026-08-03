"""Video probe + decode helpers.

MG-STUB: final — uses ffmpeg/ffprobe and OpenCV.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class MediaError(Exception):
    pass


@dataclass
class MediaInfo:
    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool
    codec: str


async def ffprobe(path: str) -> MediaInfo:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise MediaError(f"ffprobe failed: {stderr.decode()[:500]}")
    info = json.loads(stdout)
    duration_s = float(info.get("format", {}).get("duration", 0))
    duration_ms = int(duration_s * 1000)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaError("No video stream")
    fps = 30.0
    if "r_frame_rate" in video:
        num, den = video["r_frame_rate"].split("/")
        if float(den) > 0:
            fps = float(num) / float(den)
    return MediaInfo(
        duration_ms=duration_ms,
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        fps=fps,
        has_audio=audio is not None,
        codec=video.get("codec_name", "unknown"),
    )


async def extract_audio_pcm(video_path: str, out_path: str) -> None:
    """Extract mono 16kHz PCM float32 WAV."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        out_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise MediaError(f"ffmpeg audio extract failed: {stderr.decode()[:500]}")


def read_wav_float32(path: str) -> tuple[np.ndarray, int]:
    import wave

    import numpy as np

    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, sr


def decode_video_bgr24(video_path: str) -> Iterator[np.ndarray]:
    """Yield decoded frames without retaining the full clip in RAM."""
    import cv2

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise MediaError("Cannot open video")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            yield frame
    finally:
        capture.release()


async def cut_clip(video_path: str, start_ms: int, end_ms: int, out_path: str) -> None:
    start_s = max(0, start_ms / 1000)
    dur_s = max(0.1, (end_ms - start_ms) / 1000)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_s:.3f}",
        "-i",
        video_path,
        "-t",
        f"{dur_s:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        out_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise MediaError(f"ffmpeg cut failed: {stderr.decode()[:500]}")
