# Module 43: Canvas-overlay synchronous comparator

**Путь:** `apps/admin/src/features/comparator/`

## Цель
Синхронное воспроизведение 1-4 видео с overlay landmarks для визуального сравнения произнесённых слов/словосочетаний. Используется на:
- `/analyses/:id/compare` — probe vs baseline клипы.
- `/words/:word/compare` — несколько verified-прогонов одного слова.
- `/reviews/:id` — ревью с side-by-side.

## Архитектура

```
<SyncPlayer>
  ├── Hidden <video> × N (для frame-accurate seek)
  ├── Offscreen <canvas> × N (для sampling current frame)
  ├── Visible <canvas> (главный, рендерит все дорожки + overlay)
  ├── <Timeline> (общий слайдер, маркеры слов)
  └── <Transport> (play/pause, speed, prev/next word)
```

## Алгоритм
1. `requestVideoFrameCallback` (rVFC) на каждом `<video>` — вызывает callback когда frame готов.
2. На callback: рисуем frame в offscreen canvas, копируем в visible canvas в нужную region.
3. После всех 4 видео — рисуем landmark overlay поверх.
4. Loop: пока все videos not ended → schedule rVFC.
5. `playing` state → `play()` на всех videos, синхронно (допуск ± 16 ms).
6. `seek(t)`: `currentTime = t/1000` на всех, ждём `seeked` event на последнем.

## API компонента

```typescript
interface SyncTrack {
  id: string;
  videoUrl: string;
  landmarksUrl?: string;   // .npz URL
  startMs: number;
  endMs: number;
  label?: string;
  color?: string;          // для overlay
}

interface SyncPlayerProps {
  tracks: SyncTrack[];     // 1..4
  autoPlay?: boolean;
  onTimeUpdate?: (timeMs: number) => void;
  onWordClick?: (trackId: string, word: string) => void;
  markers?: { timeMs: number; label: string; trackId?: string }[];
}
```

## Файлы

### `SyncPlayer.tsx`
```typescript
/**
 * MG-STUB: реализовать canvas-overlay синхронизированный плеер.
 * Использует requestVideoFrameCallback с fallback на rAF.
 */
import { useEffect, useRef, useState } from 'react';

export function SyncPlayer({ tracks, autoPlay, onTimeUpdate, markers }: SyncPlayerProps) {
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([]);
  const visibleCanvasRef = useRef<HTMLCanvasElement>(null);
  const [playing, setPlaying] = useState(false);
  const [timeMs, setTimeMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [landmarks, setLandmarks] = useState<Map<string, LandmarkData[]>>(new Map());

  // Setup: load landmarks for each track
  useEffect(() => {
    tracks.forEach(async (t, i) => {
      if (t.landmarksUrl) {
        const res = await fetch(t.landmarksUrl);
        const buf = await res.arrayBuffer();
        const data = await parseNpz(buf);  // returns frames × 478 × 3
        setLandmarks(prev => new Map(prev).set(t.id, data));
      }
    });
  }, [tracks]);

  // Setup: get max duration
  useEffect(() => {
    const maxEnd = Math.max(...tracks.map(t => t.endMs));
    setDurationMs(maxEnd);
  }, [tracks]);

  // rVFC draw loop
  useEffect(() => {
    if (!playing) return;
    let cancelled = false;
    const drawAll = () => {
      if (cancelled) return;
      const canvas = visibleCanvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d')!;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // layout: 1 row × N cols (или 2×2)
      const cols = Math.min(tracks.length, 2);
      const rows = Math.ceil(tracks.length / cols);
      const w = canvas.width / cols;
      const h = canvas.height / rows;

      tracks.forEach((track, i) => {
        const video = videoRefs.current[i];
        if (!video || video.readyState < 2) return;
        const r = Math.floor(i / cols);
        const c = i % cols;
        const x = c * w;
        const y = r * h;
        ctx.drawImage(video, x, y, w, h);

        // overlay landmarks
        const localTimeMs = video.currentTime * 1000 - track.startMs;
        if (localTimeMs >= 0 && landmarks.has(track.id)) {
          const frameIdx = Math.floor((localTimeMs / 1000) * 30);  // assume 30 fps
          const lm = landmarks.get(track.id)![frameIdx];
          if (lm) {
            drawLandmarks(ctx, lm, x, y, w, h, track.color ?? '#fff');
          }
        }
      });

      // Update time
      const newTime = Math.max(...videoRefs.current.filter(Boolean).map(v => v!.currentTime * 1000));
      setTimeMs(newTime);
      onTimeUpdate?.(newTime);

      if ('requestVideoFrameCallback' in HTMLVideoElement.prototype) {
        videoRefs.current.forEach(v => {
          if (v) (v as any).requestVideoFrameCallback(drawAll);
        });
      } else {
        requestAnimationFrame(drawAll);
      }
    };
    drawAll();
    return () => { cancelled = true; };
  }, [playing, tracks, landmarks]);

  // play/pause all
  useEffect(() => {
    videoRefs.current.forEach(v => {
      if (!v) return;
      if (playing) v.play().catch(() => {});
      else v.pause();
    });
  }, [playing]);

  // seek all
  const seek = (ms: number) => {
    videoRefs.current.forEach((v, i) => {
      if (!v) return;
      const localMs = ms - tracks[i].startMs;
      if (localMs < 0) return;
      v.currentTime = localMs / 1000;
    });
  };

  return (
    <div className="sync-player">
      <canvas ref={visibleCanvasRef} width={1280} height={480} />
      {tracks.map((t, i) => (
        <video
          key={t.id}
          ref={el => { videoRefs.current[i] = el; }}
          src={t.videoUrl}
          crossOrigin="anonymous"
          preload="auto"
          muted
          playsInline
        />
      ))}
      <Timeline
        durationMs={durationMs}
        currentMs={timeMs}
        onSeek={seek}
        markers={markers}
      />
      <Transport
        playing={playing}
        onPlayPause={() => setPlaying(p => !p)}
      />
    </div>
  );
}
```

### `landmarks.ts`
```typescript
/**
 * Парсинг landmarks.npz (server-side exported).
 */
import { inflate } from 'pako';

export interface LandmarkData {
  timestamp_ms: number;
  points: Float32Array;  // 478 × 3 = 1434 floats
  confidence: number;
  head_pose: { yaw: number; pitch: number; roll: number };
}

export async function parseNpz(buffer: ArrayBuffer): Promise<LandmarkData[]> {
  // npz = zip containing npy files
  // Use a lib like `npz-js` or implement minimal zip reader
  // For v1 — server exports a custom binary format:
  //   magic 'MGML' (4 bytes)
  //   n_frames uint32
  //   for each frame: ts_ms uint64, n_points uint16, points float32×n×3, confidence float32, pose 3×float32
  const view = new DataView(buffer);
  const magic = String.fromCharCode(...view.getUint8(0, 4));
  if (magic !== 'MGML') throw new Error('Not MGML format');
  let offset = 4;
  const n = view.getUint32(offset, true); offset += 4;
  const out: LandmarkData[] = [];
  for (let i = 0; i < n; i++) {
    const ts = Number(view.getBigUint64(offset, true)); offset += 8;
    const nPoints = view.getUint16(offset, true); offset += 2;
    const points = new Float32Array(buffer, offset, nPoints * 3);
    offset += nPoints * 3 * 4;
    const confidence = view.getFloat32(offset, true); offset += 4;
    const yaw = view.getFloat32(offset, true); offset += 4;
    const pitch = view.getFloat32(offset, true); offset += 4;
    const roll = view.getFloat32(offset, true); offset += 4;
    out.push({ timestamp_ms: ts, points, confidence, head_pose: { yaw, pitch, roll } });
  }
  return out;
}
```

### `LandmarkOverlay.ts`
```typescript
/**
 * Drawing helpers.
 */
const FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109];
const LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78, 191, 80, 81, 82];
const LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246];
const RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398];
const LEFT_EYEBROW = [70, 63, 105, 66, 107];
const RIGHT_EYEBROW = [336, 296, 334, 293, 300];

export function drawLandmarks(
  ctx: CanvasRenderingContext2D,
  landmarks: LandmarkData,
  x: number, y: number, w: number, h: number,
  color: string
) {
  // points in image-normalized [0..1], z is relative
  const points2d: Array<[number, number]> = [];
  for (let i = 0; i < landmarks.points.length / 3; i++) {
    points2d.push([landmarks.points[i*3], landmarks.points[i*3+1]]);
  }

  ctx.save();
  ctx.translate(x, y);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 1.5;
  ctx.globalAlpha = 0.85;

  // Draw connections
  drawPath(ctx, points2d, FACE_OVAL, w, h);
  drawPath(ctx, points2d, LIPS, w, h);
  drawPath(ctx, points2d, LEFT_EYE, w, h);
  drawPath(ctx, points2d, RIGHT_EYE, w, h);
  drawPath(ctx, points2d, LEFT_EYEBROW, w, h);
  drawPath(ctx, points2d, RIGHT_EYEBROW, w, h);

  // Draw dots
  for (const [px, py] of points2d) {
    ctx.beginPath();
    ctx.arc(px * w, py * h, 1.5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawPath(
  ctx: CanvasRenderingContext2D,
  pts: Array<[number, number]>,
  indices: number[],
  w: number, h: number
) {
  ctx.beginPath();
  indices.forEach((i, j) => {
    const [px, py] = pts[i];
    if (j === 0) ctx.moveTo(px * w, py * h);
    else ctx.lineTo(px * w, py * h);
  });
  ctx.closePath();
  ctx.stroke();
}
```

### `Timeline.tsx`
```typescript
/**
 * Горизонтальный слайдер с маркерами слов.
 */
export function Timeline({ durationMs, currentMs, markers, onSeek }: TimelineProps) {
  return (
    <div className="timeline">
      <div className="timeline__track" onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const ratio = (e.clientX - rect.left) / rect.width;
        onSeek(ratio * durationMs);
      }}>
        <div className="timeline__progress" style={{ width: `${(currentMs / durationMs) * 100}%` }} />
        {markers?.map((m, i) => (
          <button
            key={i}
            className="timeline__marker"
            style={{ left: `${(m.timeMs / durationMs) * 100}%` }}
            title={m.label}
            onClick={(e) => { e.stopPropagation(); onSeek(m.timeMs); }}
          >
            <span>{m.label}</span>
          </button>
        ))}
      </div>
      <div className="timeline__time">
        {formatTime(currentMs)} / {formatTime(durationMs)}
      </div>
    </div>
  );
}
```

## Performance
- 4 видео 480p, 30 fps, 1 сек → 4 × 30 = 120 frames. M2 Pro — 60 fps.
- Landmarks overlay: 478 точек × 4 = 1912 точек + ~6 path = 1918 draw calls/frame. Native canvas — OK.
- Для 4K видео: downscale до 720p перед overlay.

## Fallback
- `requestVideoFrameCallback` доступен в Chromium 83+, Safari TP 16.4+. Fallback — `requestAnimationFrame` + `video.currentTime` polling.
