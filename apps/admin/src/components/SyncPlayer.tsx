// Canvas-overlay synchronous video player.
// 1..4 tracks with per-frame sync via requestVideoFrameCallback.
// Landmarks drawn on top of the visible canvas from in-memory .mgml/.npz data.

import { useEffect, useRef, useState, useCallback } from 'react';
import { formatTime } from '../lib/format';

export interface SyncTrack {
  id: string;
  videoUrl: string;
  landmarks?: { points: Float32Array; confidence: number }[] | null;
  startMs: number;
  endMs: number;
  label?: string;
  color?: string;
}

export interface Marker {
  timeMs: number;
  label: string;
  trackId?: string;
}

export interface SyncPlayerProps {
  tracks: SyncTrack[];
  autoPlay?: boolean;
  markers?: Marker[];
  height?: number;
  onTimeUpdate?: (timeMs: number) => void;
  onWordClick?: (trackId: string, word: string) => void;
}

const PALETTE = ['#ffffff', '#ffd166', '#06d6a0', '#ef476f'];

export function SyncPlayer({
  tracks,
  autoPlay = false,
  markers = [],
  height = 480,
  onTimeUpdate,
}: SyncPlayerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([]);
  const [playing, setPlaying] = useState(false);
  const [timeMs, setTimeMs] = useState(0);
  const durationMs = Math.max(...tracks.map((t) => t.endMs), 0);

  // Compute layout: 1×N or 2×N
  const cols = Math.min(tracks.length, 2);
  const rows = Math.ceil(tracks.length / cols);
  const cellW = 640;
  const cellH = Math.max(240, height / rows);
  const canvasW = cellW * cols;
  const canvasH = cellH * rows;

  // rVFC draw loop
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvasW, canvasH);

    let currentTime = 0;
    tracks.forEach((track, i) => {
      const video = videoRefs.current[i];
      const _r = Math.floor(i / cols);
      const _c = i % cols;
      const x = _c * cellW;
      const y = _r * cellH;
      if (video && video.readyState >= 2) {
        ctx.drawImage(video, x, y, cellW, cellH);
        currentTime = Math.max(currentTime, video.currentTime * 1000);
        // Overlay landmarks
        if (track.landmarks && track.landmarks.length > 0) {
          const localTimeMs = video.currentTime * 1000 - track.startMs;
          if (localTimeMs >= 0) {
            const fps = 30;
            const frameIdx = Math.max(0, Math.min(track.landmarks.length - 1, Math.floor((localTimeMs / 1000) * fps)));
            const lm = track.landmarks[frameIdx];
            if (lm && lm.confidence > 0.3) {
              drawLandmarks(ctx, lm.points, x, y, cellW, cellH, track.color ?? PALETTE[i % PALETTE.length]);
            }
          }
        }
        // Label
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(x + 8, y + 8, (track.label?.length ?? 6) * 8 + 16, 22);
        ctx.fillStyle = '#fff';
        ctx.font = '12px Inter, sans-serif';
        ctx.fillText(track.label ?? `Track ${i + 1}`, x + 16, y + 23);
      } else {
        ctx.fillStyle = '#222';
        ctx.fillRect(x, y, cellW, cellH);
        ctx.fillStyle = '#999';
        ctx.font = '14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`Loading track ${i + 1}…`, x + cellW / 2, y + cellH / 2);
        ctx.textAlign = 'start';
      }
    });

    setTimeMs(currentTime);
    onTimeUpdate?.(currentTime);

    if (playing) {
      const anyVFC = videoRefs.current.some(
        (v) => v && 'requestVideoFrameCallback' in v,
      );
      if (anyVFC) {
        videoRefs.current.forEach((v) => {
          if (v && 'requestVideoFrameCallback' in v) {
            (v as any).requestVideoFrameCallback(draw);
          }
        });
      } else {
        requestAnimationFrame(draw);
      }
    }
  }, [tracks, cols, cellW, cellH, canvasW, canvasH, playing, onTimeUpdate]);

  // rVFC loop
  useEffect(() => {
    if (!playing) return;
    let cancelled = false;
    const loop = () => {
      if (cancelled) return;
      draw();
      requestAnimationFrame(loop);
    };
    loop();
    return () => {
      cancelled = true;
    };
  }, [playing, draw]);

  // play/pause
  useEffect(() => {
    videoRefs.current.forEach((v) => {
      if (!v) return;
      if (playing) {
        v.play().catch(() => {
          // autoplay blocked — will resume on click
        });
      } else {
        v.pause();
      }
    });
  }, [playing]);

  // initial draw
  useEffect(() => {
    draw();
  }, [draw]);

  // autoplay if requested
  useEffect(() => {
    if (autoPlay) setPlaying(true);
  }, [autoPlay]);

  const seek = (ms: number) => {
    videoRefs.current.forEach((v, i) => {
      if (!v) return;
      const localMs = Math.max(0, ms - tracks[i].startMs);
      v.currentTime = localMs / 1000;
    });
    // Force one draw
    setTimeout(() => draw(), 50);
  };

  return (
    <div className="sync-player" style={{ aspectRatio: `${canvasW} / ${canvasH}` }}>
      <canvas
        ref={canvasRef}
        className="sync-player__canvas"
        width={canvasW}
        height={canvasH}
        aria-label="Синхронизированный просмотр видео с overlay landmarks"
      />
      {/* Hidden video elements for sampling */}
      <div className="sync-player__videos" aria-hidden>
        {tracks.map((t, i) => (
          <video
            key={t.id}
            ref={(el) => {
              videoRefs.current[i] = el;
            }}
            src={t.videoUrl}
            crossOrigin="anonymous"
            preload="auto"
            muted
            playsInline
          />
        ))}
      </div>

      <div
        className="sync-player__timeline"
        role="slider"
        tabIndex={0}
        aria-label="Временная шкала"
        aria-valuemin={0}
        aria-valuemax={durationMs}
        aria-valuenow={Math.round(timeMs)}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const ratio = (e.clientX - rect.left) / rect.width;
          seek(ratio * durationMs);
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') seek(Math.max(0, timeMs - 1000));
          if (e.key === 'ArrowRight') seek(Math.min(durationMs, timeMs + 1000));
          if (e.key === ' ') {
            e.preventDefault();
            setPlaying((p) => !p);
          }
        }}
      >
        <div className="sync-player__progress" style={{ width: `${(timeMs / durationMs) * 100}%` }} />
        {markers.map((m, i) => (
          <div
            key={i}
            className="sync-player__marker"
            style={{ left: `${(m.timeMs / durationMs) * 100}%` }}
            title={m.label}
          >
            <div className="sync-player__marker-label">{m.label}</div>
          </div>
        ))}
      </div>

      <div className="sync-player__controls">
        <button
          className="btn btn--sm"
          onClick={() => seek(Math.max(0, timeMs - 1000))}
          aria-label="Назад 1 сек"
        >
          ‹
        </button>
        <button
          className="btn btn--sm"
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? 'Пауза' : 'Воспроизвести'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <button
          className="btn btn--sm"
          onClick={() => seek(Math.min(durationMs, timeMs + 1000))}
          aria-label="Вперёд 1 сек"
        >
          ›
        </button>
        <span className="sync-player__time">
          {formatTime(timeMs)} / {formatTime(durationMs)}
        </span>
      </div>
    </div>
  );
}

// MediaPipe Face Mesh (478 points) skeleton subset.
const FACE_OVAL = [
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
];
const LIPS = [
  61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78, 191, 80, 81, 82,
];
const LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246];
const RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398];
const LEFT_EYEBROW = [70, 63, 105, 66, 107];
const RIGHT_EYEBROW = [336, 296, 334, 293, 300];

function drawLandmarks(
  ctx: CanvasRenderingContext2D,
  points: Float32Array,
  ox: number,
  oy: number,
  w: number,
  h: number,
  color: string,
) {
  const N = points.length / 3;
  const pts: Array<[number, number]> = new Array(N);
  for (let i = 0; i < N; i++) {
    pts[i] = [points[i * 3], points[i * 3 + 1]];
  }
  ctx.save();
  ctx.translate(ox, oy);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 1.2;
  ctx.globalAlpha = 0.9;
  drawPath(ctx, pts, FACE_OVAL, w, h, true);
  drawPath(ctx, pts, LIPS, w, h, true);
  drawPath(ctx, pts, LEFT_EYE, w, h, false);
  drawPath(ctx, pts, RIGHT_EYE, w, h, false);
  drawPath(ctx, pts, LEFT_EYEBROW, w, h, false);
  drawPath(ctx, pts, RIGHT_EYEBROW, w, h, false);
  ctx.globalAlpha = 0.6;
  for (let i = 0; i < N; i++) {
    const [x, y] = pts[i];
    ctx.beginPath();
    ctx.arc(x * w, y * h, 1.2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawPath(
  ctx: CanvasRenderingContext2D,
  pts: Array<[number, number]>,
  indices: number[],
  w: number,
  h: number,
  close: boolean,
) {
  ctx.beginPath();
  indices.forEach((i, j) => {
    const [x, y] = pts[i];
    if (j === 0) ctx.moveTo(x * w, y * h);
    else ctx.lineTo(x * w, y * h);
  });
  if (close) ctx.closePath();
  ctx.stroke();
}
