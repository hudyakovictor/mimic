import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { formatTime } from '../lib/format';

export interface SyncTrack {
  id: string;
  videoUrl: string;
  landmarks?: { points: Float32Array; confidence: number }[] | null;
  landmarkFps?: number;
  /** Source-video in/out points. The shared comparison timeline always starts at zero. */
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

const PALETTE = ['#f7f8fa', '#ffd166', '#06d6a0', '#ef476f'];
const SYNC_TOLERANCE_SECONDS = 0.08;

export function SyncPlayer({
  tracks,
  autoPlay = false,
  markers = [],
  height = 480,
  onTimeUpdate,
}: SyncPlayerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([]);
  const frameRef = useRef<number | null>(null);
  const timeRef = useRef(0);
  const lastSyncRef = useRef(0);
  const [playing, setPlaying] = useState(false);
  const [timeMs, setTimeMs] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [showOverlay, setShowOverlay] = useState(true);
  const [audioTrack, setAudioTrack] = useState(0);
  const [mediaErrors, setMediaErrors] = useState<Set<number>>(new Set());

  const durationMs = Math.max(
    1,
    ...tracks.map((track) => Math.max(0, track.endMs - track.startMs)),
  );
  const cols = Math.min(Math.max(tracks.length, 1), 2);
  const rows = Math.ceil(Math.max(tracks.length, 1) / cols);
  const cellW = 640;
  const cellH = Math.max(240, Math.round(height / rows));
  const canvasW = cellW * cols;
  const canvasH = cellH * rows;

  const trackDurations = useMemo(
    () => tracks.map((track) => Math.max(0, track.endMs - track.startMs)),
    [tracks],
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    context.fillStyle = '#080a0c';
    context.fillRect(0, 0, canvasW, canvasH);

    tracks.forEach((track, index) => {
      const video = videoRefs.current[index];
      const row = Math.floor(index / cols);
      const column = index % cols;
      const cellX = column * cellW;
      const cellY = row * cellH;
      context.save();
      context.beginPath();
      context.rect(cellX, cellY, cellW, cellH);
      context.clip();

      let contentX = cellX;
      let contentY = cellY;
      let contentW = cellW;
      let contentH = cellH;
      if (video && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0) {
        const mediaRatio = video.videoWidth / video.videoHeight;
        const cellRatio = cellW / cellH;
        if (mediaRatio > cellRatio) {
          contentH = cellW / mediaRatio;
          contentY += (cellH - contentH) / 2;
        } else {
          contentW = cellH * mediaRatio;
          contentX += (cellW - contentW) / 2;
        }
        context.drawImage(video, contentX, contentY, contentW, contentH);
      } else {
        context.fillStyle = '#171a1f';
        context.fillRect(cellX, cellY, cellW, cellH);
        context.fillStyle = '#89919c';
        context.textAlign = 'center';
        context.font = '14px Inter, sans-serif';
        context.fillText(
          mediaErrors.has(index) ? 'Видео недоступно' : 'Загрузка видео…',
          cellX + cellW / 2,
          cellY + cellH / 2,
        );
        context.textAlign = 'start';
      }

      if (showOverlay && track.landmarks?.length) {
        const localTimeMs = Math.max(0, (video?.currentTime ?? track.startMs / 1000) * 1000 - track.startMs);
        const frameIndex = Math.min(
          track.landmarks.length - 1,
          Math.max(0, Math.round((localTimeMs / 1000) * (track.landmarkFps || 30))),
        );
        const frame = track.landmarks[frameIndex];
        if (frame?.confidence > 0.3) {
          drawLandmarks(
            context,
            frame.points,
            contentX,
            contentY,
            contentW,
            contentH,
            track.color ?? PALETTE[index % PALETTE.length],
          );
        }
      }

      const label = track.label ?? `Дорожка ${index + 1}`;
      context.font = '600 12px Inter, sans-serif';
      const labelWidth = Math.min(cellW - 16, context.measureText(label).width + 22);
      context.fillStyle = 'rgba(8, 10, 12, .72)';
      context.fillRect(cellX + 8, cellY + 8, labelWidth, 24);
      context.fillStyle = track.color ?? PALETTE[index % PALETTE.length];
      context.fillRect(cellX + 12, cellY + 14, 3, 12);
      context.fillStyle = '#fff';
      context.fillText(label, cellX + 20, cellY + 24);

      if (timeRef.current > trackDurations[index]) {
        context.fillStyle = 'rgba(8, 10, 12, .45)';
        context.fillRect(cellX, cellY, cellW, cellH);
        context.fillStyle = '#fff';
        context.textAlign = 'center';
        context.fillText('Фрагмент завершён', cellX + cellW / 2, cellY + cellH / 2);
        context.textAlign = 'start';
      }
      context.restore();
    });
  }, [canvasH, canvasW, cellH, cols, mediaErrors, showOverlay, trackDurations, tracks]);

  const seek = useCallback(
    (requestedMs: number) => {
      const sharedMs = Math.max(0, Math.min(requestedMs, durationMs));
      timeRef.current = sharedMs;
      setTimeMs(sharedMs);
      videoRefs.current.forEach((video, index) => {
        if (!video || !tracks[index]) return;
        const localMs = Math.min(sharedMs, trackDurations[index]);
        video.currentTime = (tracks[index].startMs + localMs) / 1000;
      });
      window.setTimeout(draw, 40);
      onTimeUpdate?.(sharedMs);
    },
    [draw, durationMs, onTimeUpdate, trackDurations, tracks],
  );

  const tick = useCallback(
    (timestamp: number) => {
      const masterIndex = trackDurations.reduce(
        (best, duration, index) =>
          videoRefs.current[index] && (best < 0 || duration > trackDurations[best]) ? index : best,
        -1,
      );
      const master = masterIndex >= 0 ? videoRefs.current[masterIndex] : null;
      if (master && master.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        const sharedMs = Math.max(
          0,
          Math.min(trackDurations[masterIndex], master.currentTime * 1000 - tracks[masterIndex].startMs),
        );
        timeRef.current = sharedMs;
        setTimeMs(sharedMs);
        onTimeUpdate?.(sharedMs);

        if (timestamp - lastSyncRef.current > 250) {
          videoRefs.current.forEach((video, index) => {
            if (!video || video === master || sharedMs >= trackDurations[index]) return;
            const expected = (tracks[index].startMs + sharedMs) / 1000;
            if (Math.abs(video.currentTime - expected) > SYNC_TOLERANCE_SECONDS) {
              video.currentTime = expected;
            }
          });
          lastSyncRef.current = timestamp;
        }
        if (sharedMs >= durationMs - 10) setPlaying(false);
      }
      draw();
      if (playing) frameRef.current = requestAnimationFrame(tick);
    },
    [draw, durationMs, onTimeUpdate, playing, trackDurations, tracks],
  );

  useEffect(() => {
    if (!playing) {
      if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
      draw();
      return;
    }
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
    };
  }, [draw, playing, tick]);

  useEffect(() => {
    videoRefs.current.forEach((video, index) => {
      if (!video) return;
      video.playbackRate = playbackRate;
      video.muted = index !== audioTrack;
      const endedForSharedTimeline = timeRef.current >= trackDurations[index];
      if (playing && !endedForSharedTimeline) video.play().catch(() => setPlaying(false));
      else video.pause();
    });
  }, [audioTrack, playbackRate, playing, trackDurations]);

  const trackSignature = tracks
    .map((track) => `${track.id}:${track.videoUrl}:${track.startMs}:${track.endMs}`)
    .join('|');

  useEffect(() => {
    videoRefs.current = videoRefs.current.slice(0, tracks.length);
    setMediaErrors((current) => (current.size ? new Set() : current));
    setAudioTrack(0);
    timeRef.current = 0;
    setTimeMs(0);
    videoRefs.current.forEach((video, index) => {
      if (video && tracks[index]) video.currentTime = tracks[index].startMs / 1000;
    });
    // Track identity, not the array reference, defines a new comparison.
  }, [trackSignature]);

  useEffect(() => {
    if (autoPlay) setPlaying(true);
  }, [autoPlay]);

  const togglePlaying = () => {
    if (timeRef.current >= durationMs - 10) seek(0);
    setPlaying((current) => !current);
  };

  const safeProgress = durationMs > 0 ? (timeMs / durationMs) * 100 : 0;

  return (
    <div className="sync-player">
      <canvas
        ref={canvasRef}
        className="sync-player__canvas"
        width={canvasW}
        height={canvasH}
        style={{ aspectRatio: `${canvasW} / ${canvasH}` }}
        role="img"
        aria-label="Синхронизированное сравнение видео с ключевыми точками лица"
      />
      <div className="sync-player__videos" aria-hidden>
        {tracks.map((track, index) => (
          <video
            key={track.id}
            ref={(element) => {
              videoRefs.current[index] = element;
            }}
            src={track.videoUrl}
            crossOrigin="anonymous"
            preload="auto"
            playsInline
            onLoadedData={() => {
              const video = videoRefs.current[index];
              if (video) video.currentTime = track.startMs / 1000;
              window.setTimeout(draw, 30);
            }}
            onSeeked={draw}
            onError={() => setMediaErrors((current) => new Set(current).add(index))}
          />
        ))}
      </div>

      <div
        className="sync-player__timeline"
        role="slider"
        tabIndex={0}
        aria-label="Общая временная шкала"
        aria-valuemin={0}
        aria-valuemax={durationMs}
        aria-valuenow={Math.round(timeMs)}
        onClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          seek(((event.clientX - rect.left) / rect.width) * durationMs);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowLeft') seek(timeMs - 500);
          if (event.key === 'ArrowRight') seek(timeMs + 500);
          if (event.key === ' ') {
            event.preventDefault();
            togglePlaying();
          }
        }}
      >
        <div className="sync-player__progress" style={{ width: `${safeProgress}%` }} />
        {markers.map((marker, index) => (
          <div
            key={`${marker.timeMs}-${marker.label}-${index}`}
            className="sync-player__marker"
            style={{ left: `${(marker.timeMs / durationMs) * 100}%` }}
            title={marker.label}
          >
            <div className="sync-player__marker-label">{marker.label}</div>
          </div>
        ))}
      </div>

      <div className="sync-player__controls">
        <button className="btn btn--sm" type="button" onClick={() => seek(timeMs - 500)} aria-label="Назад на полсекунды">−0.5</button>
        <button className="btn btn--sm sync-player__play" type="button" onClick={togglePlaying} aria-label={playing ? 'Пауза' : 'Воспроизвести'}>
          {playing ? '❚❚' : '▶'}
        </button>
        <button className="btn btn--sm" type="button" onClick={() => seek(timeMs + 500)} aria-label="Вперёд на полсекунды">+0.5</button>
        <button
          className={`btn btn--sm ${showOverlay ? '' : 'btn--secondary'}`}
          type="button"
          onClick={() => setShowOverlay((current) => !current)}
          aria-pressed={showOverlay}
        >
          Точки
        </button>
        <select className="select sync-player__select" value={playbackRate} onChange={(event) => setPlaybackRate(Number(event.target.value))} aria-label="Скорость">
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={1.5}>1.5×</option>
          <option value={2}>2×</option>
        </select>
        {tracks.length > 1 && (
          <select className="select sync-player__select" value={audioTrack} onChange={(event) => setAudioTrack(Number(event.target.value))} aria-label="Звуковая дорожка">
            {tracks.map((track, index) => <option key={track.id} value={index}>Звук: {track.label ?? index + 1}</option>)}
          </select>
        )}
        <span className="sync-player__time">{formatTime(timeMs)} / {formatTime(durationMs)}</span>
      </div>
    </div>
  );
}

const FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109];
const LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78, 191, 80, 81, 82];
const LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246];
const RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398];
const LEFT_EYEBROW = [70, 63, 105, 66, 107];
const RIGHT_EYEBROW = [336, 296, 334, 293, 300];

function drawLandmarks(
  context: CanvasRenderingContext2D,
  points: Float32Array,
  offsetX: number,
  offsetY: number,
  width: number,
  height: number,
  color: string,
) {
  const count = points.length / 3;
  const coordinates: Array<[number, number]> = new Array(count);
  for (let index = 0; index < count; index += 1) {
    coordinates[index] = [points[index * 3], points[index * 3 + 1]];
  }
  context.save();
  context.translate(offsetX, offsetY);
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = 1.25;
  context.globalAlpha = 0.92;
  drawPath(context, coordinates, FACE_OVAL, width, height, true);
  drawPath(context, coordinates, LIPS, width, height, true);
  drawPath(context, coordinates, LEFT_EYE, width, height, true);
  drawPath(context, coordinates, RIGHT_EYE, width, height, true);
  drawPath(context, coordinates, LEFT_EYEBROW, width, height, false);
  drawPath(context, coordinates, RIGHT_EYEBROW, width, height, false);
  context.globalAlpha = 0.48;
  for (let index = 0; index < count; index += 1) {
    const [x, y] = coordinates[index];
    context.beginPath();
    context.arc(x * width, y * height, 1.05, 0, Math.PI * 2);
    context.fill();
  }
  context.restore();
}

function drawPath(
  context: CanvasRenderingContext2D,
  points: Array<[number, number]>,
  indices: number[],
  width: number,
  height: number,
  close: boolean,
) {
  context.beginPath();
  indices.forEach((index, pathIndex) => {
    const point = points[index];
    if (!point) return;
    if (pathIndex === 0) context.moveTo(point[0] * width, point[1] * height);
    else context.lineTo(point[0] * width, point[1] * height);
  });
  if (close) context.closePath();
  context.stroke();
}
