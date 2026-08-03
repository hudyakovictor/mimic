"""Word-to-landmark alignment.

MG-STUB: final.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

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
    if target_len <= 0:
        raise ValueError("target_len must be positive")
    arr = np.asarray(arr)
    if arr.ndim not in (1, 2):
        raise ValueError("arr must be a 1D or 2D array")
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
        out[:, d] = np.interp(x_new, x_old, arr[:, d])
    return out


def _normalize_text(value: object) -> str:
    """Canonicalize ASR tokens without destroying letters from non-Latin scripts."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = re.sub(r"[^\w'-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip(" _'-")


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
    normalized_landmarks = np.asarray(normalized_landmarks)
    audio = np.asarray(audio)
    if normalized_landmarks.ndim != 2:
        raise ValueError("normalized_landmarks must have shape (frames, features)")
    if audio.ndim != 1:
        raise ValueError("audio must be mono")
    if fps <= 0 or audio_sample_rate <= 0:
        raise ValueError("fps and audio_sample_rate must be positive")
    if normalized_landmarks.shape[0] == 0 or not words:
        return out
    frame_count = normalized_landmarks.shape[0]
    normalized_words: list[dict] = []
    for source in words:
        text = _normalize_text(source.get("text"))
        if not text:
            continue
        try:
            start_ms = max(0, int(source["start_ms"]))
            end_ms = int(source["end_ms"])
        except (KeyError, TypeError, ValueError):
            continue
        if end_ms <= start_ms:
            continue
        normalized_words.append(
            {
                "text": text,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "confidence": float(np.clip(source.get("confidence", 0.0), 0.0, 1.0)),
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
        first_frame = max(0, min(frame_count, int(np.floor(start_ms / 1000 * fps))))
        last_frame = max(first_frame + 1, min(frame_count, int(np.ceil(end_ms / 1000 * fps))))
        landmark_slice = normalized_landmarks[first_frame:last_frame]
        if landmark_slice.shape[0] < 5:
            continue
        audio_start = max(0, min(audio.size, int(start_ms * audio_sample_rate / 1000)))
        audio_end = max(audio_start, min(audio.size, int(end_ms * audio_sample_rate / 1000)))
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
