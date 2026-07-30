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

    T = arr.shape[0]
    if T == target_len:
        return arr
    if T == 0:
        return np.zeros((target_len, arr.shape[1] if arr.ndim > 1 else 1), dtype=arr.dtype)
    x_old = np.linspace(0, 1, T)
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
) -> list[PhraseInstance]:
    out: list[PhraseInstance] = []
    if normalized_landmarks.shape[0] == 0 or len(words) == 0:
        return out
    T = normalized_landmarks.shape[0]
    for w in words:
        s = int(w["start_ms"])
        e = int(w["end_ms"])
        duration = e - s
        if duration < min_word_ms or duration > max_word_ms:
            continue
        i0 = max(0, min(T, int(s / 1000 * fps)))
        i1 = max(i0 + 1, min(T, int(e / 1000 * fps)))
        lm_slice = normalized_landmarks[i0:i1]
        if lm_slice.shape[0] < 5:
            continue
        lm_resampled = _resample(lm_slice, 30)
        a0 = int(s * audio_sample_rate / 1000)
        a1 = int(e * audio_sample_rate / 1000)
        audio_slice = audio[a0:a1]
        if audio_slice.size == 0:
            continue
        word = (w.get("text") or "").lower().strip(".,!?;:")
        if not word:
            continue
        out.append(
            PhraseInstance(
                word=word,
                language=language,
                start_ms=s,
                end_ms=e,
                landmarks_slice=lm_resampled,
                audio_slice=audio_slice,
                confidence=float(w.get("confidence", 0.0)),
            )
        )
    return out
