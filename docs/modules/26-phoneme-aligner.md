# Module 26: Phoneme/word alignment

**Путь:** `services/worker/app/phoneme/`

## Файлы

### `aligner.py`
```python
"""
MG-STUB: реализовать.
"""
import numpy as np
from dataclasses import dataclass

@dataclass(frozen=True)
class PhraseInstance:
    word: str
    language: str
    start_ms: int
    end_ms: int
    landmarks_slice: np.ndarray  # shape (T, n_dims)
    features_slice: np.ndarray  # shape (T, n_features) — motion features
    audio_slice: np.ndarray     # shape (N,) PCM
    confidence: float
    source_decision_id: str | None = None


class PhraseAligner:
    def __init__(self, min_word_ms: int = 150, max_word_ms: int = 2000):
        self.min_word_ms = min_word_ms
        self.max_word_ms = max_word_ms

    def align(self, transcript_words: list[dict], landmarks_seq, features_seq, audio) -> list[PhraseInstance]:
        """Map each word to:
        - landmarks slice (timestamps → frame indices)
        - features slice
        - audio slice
        - resample to fixed length 30 frames (for DTW)
        - resample audio to 0.5 s mono (for embedding)
        """
        from ..features.time_warp import resample_to_length

        out = []
        fps = landmarks_seq.source_fps
        sample_rate = 16000
        landmark_times = [f.timestamp_ms for f in landmarks_seq.frames]
        feature_times = landmark_times  # aligned 1:1
        audio_n = len(audio)

        for w in transcript_words:
            start_ms = w["start_ms"]
            end_ms = w["end_ms"]
            duration = end_ms - start_ms
            if duration < self.min_word_ms or duration > self.max_word_ms:
                continue  # skip слишком короткие / длинные

            # landmarks slice
            lmk_indices = [i for i, t in enumerate(landmark_times)
                           if start_ms <= t <= end_ms]
            if len(lmk_indices) < 10:
                continue
            lmk_slice = np.array([landmarks_seq.frames[i].points_vector for i in lmk_indices])
            feat_slice = np.array([features_seq.frames[i] for i in lmk_indices if i < len(features_seq.frames)])

            # resample
            lmk_resampled = resample_to_length(lmk_slice, 30)
            feat_resampled = resample_to_length(feat_slice, 30)

            # audio slice
            a_start = int(start_ms * sample_rate / 1000)
            a_end = int(end_ms * sample_rate / 1000)
            audio_slice = audio[a_start:a_end]
            if len(audio_slice) == 0:
                continue

            out.append(PhraseInstance(
                word=w["text"].lower().strip(".,!?;:"),
                language="auto",  # determined from transcript
                start_ms=start_ms,
                end_ms=end_ms,
                landmarks_slice=lmk_resampled,
                features_slice=feat_resampled,
                audio_slice=audio_slice,
                confidence=w.get("confidence", 0.0),
            ))
        return out
```

## Что важно
- Нормализация по длительности — критична для DTW.
- Audio нормализация по длительности — для acoustic embedding.
- Word lowercased + punctuation stripped для matching.
- Очень короткие слова (< 150 ms) и очень длинные (> 2 s) — пропускаем.
