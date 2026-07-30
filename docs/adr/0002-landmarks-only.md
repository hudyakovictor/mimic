# ADR 0002: Landmarks-only v1

**Status:** Accepted.

## Context
Видео в проде — низкого качества: webcams, телефоны, плохое освещение, дальние планы, сжатие h264 с артефактами. Texture-based методы (rPPG, skin texture, depth) ненадёжны на таких данных.

## Decision
v1 использует **только** semantic landmarks, confidence, head pose. Texture, rPPG, optical flow — исключены до отдельной валидации. Product wording — "motion inconsistency risk", не universal mask detection.

## Consequences
**Плюсы:** работает на плохом видео; меньше attack surface (нет biometric leak через skin texture); проще воспроизводимость.
**Минусы:** не сможем уловить всё; некоторые типы атак (покраска кожи) могут обойти.

## Validation
Golden-набор включает:
- 50 genuine
- 50 силиконовая маска (разные лица, разные pose)
- 50 условия плохого освещения/качества

Target: FAR < 5% @ FRR 5%.
