# ADR 0003: Statistical baseline (DTW + Mahalanobis)

**Status:** Accepted.

## Context
Нужен метод сравнения произнесённого слова в probe-видео с набором verified-прогонов того же слова от заявленного человека. Варианты:
1. **Pretrained speaker embedding** (wav2vec2, ResNet) — требует много данных для fine-tune, GPU.
2. **Small NN на landmarks** — 1D-CNN/GRU encoder + contrastive loss. Требует training infrastructure.
3. **Statistical baseline**: DTW на нормализованной кривой + Mahalanobis на региональных ratios. Полностью numpy/scipy, no GPU.

## Decision
v1 — **statistical baseline (DTW + Mahalanobis)**. Прост в реализации, прозрачен, легко интерпретируется. Нейросетевой вариант — в v2, как reranker поверх DTW-кандидатов.

## Consequences
**Плюсы:** прозрачный evidence (DTW path показывает где разошлись), работает на CPU, нет training pipeline overhead.
**Минусы:** хуже работает на коротких последовательностях (< 200 ms), не учитывает контекст соседних слов.

## Thresholds
- 3+ verified → создать template v1.
- 10+ verified → "mature" template, statistics устойчивы.
- Decision score ∈ [0, 1]: `1 - similarity`, similarity = `1 / (1 + α · DTW_dist + β · Mahalanobis)`.
- Label: `CONSISTENT` < 0.35, `SUSPICIOUS` ≥ 0.65, иначе `INSUFFICIENT_DATA`.
