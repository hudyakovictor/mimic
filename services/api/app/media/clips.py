"""Accurate, analysis-safe video clipping.

The platform deliberately stores short canonical clips instead of retaining a
large source upload.  A clip is re-encoded rather than stream-copied because
cuts on arbitrary timestamps must not snap to the previous keyframe.

The ``analysis-v1`` profile is intentionally conservative:
* H.264 High / CRF 17 keeps mouth and cheek edges useful for motion analysis;
* source cadence is preserved (capped at 60 fps by the ingest validator);
* frames are never enlarged and are bounded to 1920x1080;
* mono AAC 96 kbit/s is sufficient for ASR while remaining browser compatible;
* one-second GOPs make reviewer seeking cheap.

AV1/H.265 are useful archive codecs, but decoding differences and browser
support make them a poor 80/20 choice for the canonical evidence asset.  They
can be generated later as disposable proxies.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path


class ClipValidationError(ValueError):
    """Raised when requested intervals cannot safely be materialized."""


class ClipTranscodeError(RuntimeError):
    """Raised when ffmpeg/ffprobe rejects an input or output."""


@dataclass(frozen=True, slots=True)
class ClipSegment:
    start_ms: int
    end_ms: int
    label: str = ""

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True, slots=True)
class ClipMediaInfo:
    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool
    video_codec: str


def validate_segments(
    segments: list[ClipSegment],
    *,
    source_duration_ms: int,
    max_segments: int = 20,
    min_segment_ms: int = 500,
    max_total_ms: int = 20 * 60 * 1000,
) -> list[ClipSegment]:
    """Validate, sort and return non-overlapping source intervals.

    Rejecting overlaps avoids paying twice for the same frames and keeps
    retention accounting predictable. Adjacent intervals are allowed because
    an operator may intentionally preserve two semantic sections separately.
    """
    if source_duration_ms <= 0:
        raise ClipValidationError("Source duration is unknown")
    if not segments:
        raise ClipValidationError("Select at least one interval")
    if len(segments) > max_segments:
        raise ClipValidationError(f"At most {max_segments} intervals are allowed")

    ordered = sorted(segments, key=lambda item: (item.start_ms, item.end_ms))
    total_ms = 0
    previous_end = 0
    for index, segment in enumerate(ordered):
        if segment.start_ms < 0:
            raise ClipValidationError(f"Interval {index + 1} starts before the video")
        if segment.end_ms > source_duration_ms:
            raise ClipValidationError(f"Interval {index + 1} ends after the video")
        if segment.duration_ms < min_segment_ms:
            raise ClipValidationError(f"Interval {index + 1} must be at least {min_segment_ms} ms")
        if index and segment.start_ms < previous_end:
            raise ClipValidationError("Selected intervals must not overlap")
        previous_end = segment.end_ms
        total_ms += segment.duration_ms

    if total_ms > max_total_ms:
        raise ClipValidationError(f"Selected duration exceeds {max_total_ms // 60_000} minutes")
    return ordered


def build_ffmpeg_command(
    source_path: str,
    output_path: str,
    segment: ClipSegment,
    *,
    source_fps: float,
    has_audio: bool,
) -> list[str]:
    """Build the deterministic ``analysis-v1`` ffmpeg invocation."""
    start_s = segment.start_ms / 1000
    duration_s = segment.duration_ms / 1000
    output_fps = max(1.0, min(source_fps or 30.0, 60.0))
    video_filter = (
        "scale=w='min(iw,1920)':h='min(ih,1080)':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        # Input-side seeking is fast; re-encoding still gives a frame-accurate cut.
        "-ss",
        f"{start_s:.3f}",
        "-i",
        source_path,
        "-t",
        f"{duration_s:.3f}",
        "-map",
        "0:v:0",
    ]
    if has_audio:
        command += ["-map", "0:a:0?"]
    command += [
        "-vf",
        video_filter,
        "-r",
        f"{output_fps:.6f}",
        "-fps_mode",
        "cfr",
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-preset",
        "medium",
        "-crf",
        "17",
        "-g",
        str(max(1, round(output_fps))),
        "-keyint_min",
        str(max(1, round(output_fps))),
        "-sc_threshold",
        "0",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio:
        command += ["-c:a", "aac", "-b:a", "96k", "-ac", "1", "-ar", "48000"]
    else:
        command += ["-an"]
    command += ["-movflags", "+faststart", output_path]
    return command


async def transcode_clip(
    source_path: str,
    output_path: str,
    segment: ClipSegment,
    *,
    source_fps: float,
    has_audio: bool,
    timeout_seconds: int = 900,
) -> None:
    """Run ffmpeg and ensure it produced a non-empty MP4."""
    command = build_ffmpeg_command(
        source_path,
        output_path,
        segment,
        source_fps=source_fps,
        has_audio=has_audio,
    )
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ClipTranscodeError("ffmpeg is not installed") from exc
    try:
        _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise ClipTranscodeError("Clip transcoding timed out") from exc
    if process.returncode != 0:
        message = stderr.decode(errors="replace")[-1000:]
        raise ClipTranscodeError(f"ffmpeg failed: {message}")
    output = Path(output_path)
    if not output.is_file() or output.stat().st_size <= 0:
        raise ClipTranscodeError("ffmpeg produced an empty clip")


async def probe_media(path: str) -> ClipMediaInfo:
    """Read only the media metadata needed by clipping and validation."""
    try:
        process = await asyncio.create_subprocess_exec(
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
    except FileNotFoundError as exc:
        raise ClipTranscodeError("ffprobe is not installed") from exc
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise ClipTranscodeError(f"ffprobe failed: {stderr.decode(errors='replace')[-1000:]}")
    payload = json.loads(stdout)
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video is None:
        raise ClipTranscodeError("No video stream")
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    duration = float(payload.get("format", {}).get("duration") or video.get("duration") or 0)
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"
    try:
        numerator, denominator = rate.split("/", 1)
        fps = float(numerator) / max(float(denominator), 1e-9)
    except (TypeError, ValueError, ZeroDivisionError):
        fps = 30.0
    return ClipMediaInfo(
        duration_ms=max(0, round(duration * 1000)),
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=max(0.0, fps),
        has_audio=audio is not None,
        video_codec=str(video.get("codec_name") or "unknown"),
    )
