# Module 25: ASR (faster-whisper)

**Путь:** `services/worker/app/asr/`

## Файлы

### `whisper_engine.py`
```python
"""
MG-STUB: реализовать.
"""
from faster_whisper import WhisperModel
import numpy as np
from typing import Iterable

class WhisperEngine:
    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8", language: str | None = None):
        # auto: cuda > metal > cpu
        actual_device = self._resolve_device(device)
        self.model = WhisperModel(model_size, device=actual_device, compute_type=compute_type)
        self.language = language

    @staticmethod
    def _resolve_device(d: str) -> str:
        if d != "auto":
            return d
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        # faster-whisper doesn't support MPS yet; fall back to cpu
        return "cpu"

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> "TranscriptionResult":
        """Transcribe mono PCM 16kHz audio.
        Returns: {language, words: [{start_ms, end_ms, text, confidence}], text}
        """
        segments, info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 200},
        )
        words = []
        full_text = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    words.append({
                        "start_ms": int(w.start * 1000),
                        "end_ms": int(w.end * 1000),
                        "text": w.word.strip(),
                        "confidence": float(w.probability),
                    })
                    full_text.append(w.word)
        return TranscriptionResult(
            language=info.language,
            language_probability=info.language_probability,
            words=words,
            text=" ".join(full_text).strip(),
        )


@dataclass
class TranscriptionResult:
    language: str
    language_probability: float
    words: list[dict]
    text: str
```

### `language_detect.py`
```python
"""
MG-STUB: реализовать heuristic:
- if text has cyrillic chars > 50%: 'ru'
- elif text has latin chars > 50%: 'en'
- else: 'auto'
- либо через fasttext lid.176.bin (если установлен)
"""
```

## Models
- Dev: `small` (462 MB), int8 quantization, CPU OK.
- Production: `medium` (1.5 GB), int8, CPU OK, GPU faster.
- Large-v3: optional, для максимального качества.

## Output contract
- `Transcript` row: id, job_id, language, model_version, words (JSONB), object_key, created_at.
- `words`: список с char-level timing.

## Quality gates
- `mean_word_confidence < 0.6` → `evidence: LOW_QUALITY_AUDIO`.
- `language_probability < 0.7` → `evidence: LANGUAGE_DETECTION_UNCERTAIN`.
- `n_words == 0` → job → `INSUFFICIENT_DATA` (no speech detected).
