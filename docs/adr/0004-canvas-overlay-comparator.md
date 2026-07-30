# ADR 0004: Canvas-overlay synchronous comparator

**Status:** Accepted.

## Context
Ревьюер должен видеть несколько прогонов одного и того же слова, чтобы вручную оценить воспроизводимость. Варианты:
1. **Несколько независимых `<video>` плееров** — проще, но наглядность низкая, рассинхрон неизбежен.
2. **Один canvas-overlay** — все видео в одном кадре, общий таймлайн, общий overlay. Сложнее, но выразительно.

## Decision
**Canvas-overlay** (SyncPlayer) для 2..4 дорожек:
- Один видимый `<canvas>`, каждая дорожка в свой region.
- Общий `currentTimeMs`, `playing`, `speed`.
- `requestVideoFrameCallback` для per-frame sync.
- На каждый frame — рисуем видео + overlay landmarks (точки + скелет).

## Consequences
**Плюсы:** точная синхронизация, можно наложить траектории, ревьюер видит различия мгновенно.
**Минусы:** Safari TP поддерживает `requestVideoFrameCallback` с 16.4; для старых — fallback на `setTimeout(16)`.

## Components
- `SyncPlayer.tsx` — оркестратор.
- `VideoPlayer.tsx` — единичный плеер, hidden `<video>` + offscreen canvas для sampling.
- `LandmarkOverlay.tsx` — рисование точек поверх canvas.
- `Timeline.tsx` — общий слайдер с маркерами слов.

## Performance
- 4 видео 480p, 30 fps, 1 сек слова = 4 × 30 = 120 frames. На M2 Pro — 60 fps без проблем.
- Landmarks overlay: ~30 точек × 4 = 120 draw calls, native canvas достаточно.
