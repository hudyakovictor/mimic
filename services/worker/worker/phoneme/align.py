"""Word-to-landmark alignment.

MG-STUB: final.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PhraseInstance:
    word: str
    language: str
    start_ms: int
    end_ms: int
    landmarks_slice: np.ndarray  # (30, 33) normalized
    audio_slice: np.ndarray
    confidence: float


def _resample(arr: np.ndarray, target_len: int = 30) -> np.ndarray:
    from scipy.interpolate import interp1d

    frame_count = arr.shape[0]
    if frame_count == target_len:
        return arr
    if frame_count == 0:
        return np.zeros((target_len, arr.shape[1] if arr.ndim > 1 else 1), dtype=arr.dtype)
    x_old = np.linspace(0, 1, frame_count)
    x_new = np.linspace(0, 1, target_len)
    if arr.ndim == 1:
        return np.interp(x_new, x_old, arr).astype(arr.dtype)
    out = np.zeros((target_len, arr.shape[1]), dtype=arr.dtype)
    for d in range(arr.shape[1]):
        f = interp1d(x_old, arr[:, d], kind="linear")
        out[:, d] = f(x_new)
    return out


def align_words_to_landmarks(
    words: list[dict],
    normalized_landmarks: np.ndarray,  # (T, 33)
    audio: np.ndarray,
    audio_sample_rate: int = 16000,
    min_word_ms: int = 150,
    max_word_ms: int = 2000,
    fps: float = 30.0,
    language: str = "auto",
    max_phrase_words: int = 3,
    max_phrase_ms: int = 5000,
    max_inter_word_gap_ms: int = 450,
) -> list[PhraseInstance]:
    """Align individual words plus contiguous 2/3-word phrases.

    N-grams are deliberately capped: they give reviewers repeatable
    word-combinations without quadratic dataset growth.
    """
    out: list[PhraseInstance] = []
    if normalized_landmarks.shape[0] == 0 or not words:
        return out
    frame_count = normalized_landmarks.shape[0]
    normalized_words: list[dict] = []
    for source in words:
        text = (source.get("text") or "").lower().strip(".,!?;:")
        if not text:
            continue
        normalized_words.append(
            {
                "text": text,
                "start_ms": int(source["start_ms"]),
                "end_ms": int(source["end_ms"]),
                "confidence": float(source.get("confidence", 0.0)),
            }
        )

    candidates: list[dict] = []
    for index, item in enumerate(normalized_words):
        duration = item["end_ms"] - item["start_ms"]
        if min_word_ms <= duration <= max_word_ms:
            candidates.append(item)
        for phrase_size in range(2, max_phrase_words + 1):
            group = normalized_words[index : index + phrase_size]
            if len(group) != phrase_size:
                break
            if any(
                group[position + 1]["start_ms"] - group[position]["end_ms"] > max_inter_word_gap_ms
                for position in range(len(group) - 1)
            ):
                break
            phrase_duration = group[-1]["end_ms"] - group[0]["start_ms"]
            if phrase_duration > max_phrase_ms:
                break
            candidates.append(
                {
                    "text": " ".join(part["text"] for part in group),
                    "start_ms": group[0]["start_ms"],
                    "end_ms": group[-1]["end_ms"],
                    "confidence": min(part["confidence"] for part in group),
                }
            )

    for candidate in candidates:
        start_ms = candidate["start_ms"]
        end_ms = candidate["end_ms"]
        first_frame = max(0, min(frame_count, int(start_ms / 1000 * fps)))
        last_frame = max(first_frame + 1, min(frame_count, int(end_ms / 1000 * fps)))
        landmark_slice = normalized_landmarks[first_frame:last_frame]
        if landmark_slice.shape[0] < 5:
            continue
        audio_start = int(start_ms * audio_sample_rate / 1000)
        audio_end = int(end_ms * audio_sample_rate / 1000)
        audio_slice = audio[audio_start:audio_end]
        if audio_slice.size == 0:
            continue
        out.append(
            PhraseInstance(
                word=candidate["text"],
                language=language,
                start_ms=start_ms,
                end_ms=end_ms,
                landmarks_slice=_resample(landmark_slice, 30),
                audio_slice=audio_slice,
                confidence=candidate["confidence"],
            )
        )
    return out
