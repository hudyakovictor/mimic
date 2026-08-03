from __future__ import annotations

import pytest
from app.media.clips import (
    ClipSegment,
    ClipValidationError,
    build_ffmpeg_command,
    validate_segments,
)


def test_validate_segments_sorts_and_preserves_adjacent_ranges():
    result = validate_segments(
        [ClipSegment(5_000, 7_000, "second"), ClipSegment(1_000, 5_000, "first")],
        source_duration_ms=10_000,
    )
    assert [item.label for item in result] == ["first", "second"]
    assert sum(item.duration_ms for item in result) == 6_000


@pytest.mark.parametrize(
    ("segments", "message"),
    [
        ([], "at least one"),
        ([ClipSegment(-1, 1_000)], "starts before"),
        ([ClipSegment(0, 400)], "at least 500"),
        ([ClipSegment(0, 2_000), ClipSegment(1_500, 3_000)], "must not overlap"),
        ([ClipSegment(9_000, 11_000)], "ends after"),
    ],
)
def test_validate_segments_rejects_unsafe_ranges(segments, message):
    with pytest.raises(ClipValidationError, match=message):
        validate_segments(segments, source_duration_ms=10_000)


def test_ffmpeg_profile_is_frame_accurate_and_analysis_safe():
    command = build_ffmpeg_command(
        "/tmp/source.mov",
        "/tmp/clip.mp4",
        ClipSegment(1_250, 4_750),
        source_fps=120,
        has_audio=True,
    )
    joined = " ".join(command)
    assert "-ss 1.250" in joined
    assert "-t 3.500" in joined
    assert "-c:v libx264" in joined
    assert "-crf 17" in joined
    assert "-r 60.000000" in joined
    assert "-fps_mode cfr" in joined
    assert "-movflags +faststart" in joined
    assert "-c:a aac" in joined
