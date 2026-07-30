"""faster-whisper ASR."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Word:
    start_ms: int
    end_ms: int
    text: str
    confidence: float


@dataclass
class Transcription:
    language: str
    language_probability: float
    text: str
    words: list[Word]
    mean_confidence: float


class WhisperEngine:
    def __init__(self, model_size: str = "small", device: str = "auto", compute_type: str = "int8"):
        from faster_whisper import WhisperModel

        if device == "auto":
            device = self._resolve_device()
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.model_size = model_size

    @staticmethod
    def _resolve_device() -> str:
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def transcribe(self, audio_path: str, language: str | None = None) -> Transcription:
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 200},
        )
        words: list[Word] = []
        full_text: list[str] = []
        confidences: list[float] = []
        for seg in segments:
            if not seg.words:
                continue
            for w in seg.words:
                words.append(
                    Word(
                        start_ms=int(w.start * 1000),
                        end_ms=int(w.end * 1000),
                        text=w.word.strip(),
                        confidence=float(w.probability),
                    )
                )
                full_text.append(w.word)
                confidences.append(float(w.probability))
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return Transcription(
            language=info.language,
            language_probability=info.language_probability,
            text=" ".join(full_text).strip(),
            words=words,
            mean_confidence=mean_conf,
        )
