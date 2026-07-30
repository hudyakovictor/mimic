import { useEffect, useMemo, useRef, useState } from 'react';
import { formatTime } from '../lib/format';

export interface SelectedInterval {
  startMs: number;
  endMs: number;
  label: string;
}

interface ClipEditorProps {
  videoUrl: string;
  knownDurationMs?: number;
  sourceSizeBytes?: number;
  busy?: boolean;
  onBack: () => void;
  onSubmit: (intervals: SelectedInterval[], deleteSource: boolean) => void;
}

const MIN_INTERVAL_MS = 500;
const MAX_INTERVALS = 20;
const MAX_TOTAL_MS = 20 * 60 * 1000;

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function ClipEditor({
  videoUrl,
  knownDurationMs,
  sourceSizeBytes,
  busy = false,
  onBack,
  onSubmit,
}: ClipEditorProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [durationMs, setDurationMs] = useState(knownDurationMs ?? 0);
  const [currentMs, setCurrentMs] = useState(0);
  const [draftStartMs, setDraftStartMs] = useState(0);
  const [draftEndMs, setDraftEndMs] = useState(Math.min(knownDurationMs ?? 30_000, 30_000));
  const [intervals, setIntervals] = useState<SelectedInterval[]>([]);
  const [deleteSource, setDeleteSource] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!knownDurationMs) return;
    setDurationMs(knownDurationMs);
    setDraftEndMs((current) => (current > 0 ? Math.min(current, knownDurationMs) : Math.min(30_000, knownDurationMs)));
  }, [knownDurationMs]);

  const totalMs = useMemo(
    () => intervals.reduce((sum, interval) => sum + interval.endMs - interval.startMs, 0),
    [intervals],
  );

  const seek = (timeMs: number) => {
    const next = clamp(timeMs, 0, durationMs);
    if (videoRef.current) videoRef.current.currentTime = next / 1000;
    setCurrentMs(next);
  };

  const addInterval = () => {
    setError(null);
    const startMs = Math.round(Math.min(draftStartMs, draftEndMs));
    const endMs = Math.round(Math.max(draftStartMs, draftEndMs));
    if (endMs - startMs < MIN_INTERVAL_MS) {
      setError('Фрагмент должен быть не короче 0,5 секунды.');
      return;
    }
    if (intervals.length >= MAX_INTERVALS) {
      setError(`Можно выбрать не более ${MAX_INTERVALS} фрагментов.`);
      return;
    }
    if (intervals.some((item) => startMs < item.endMs && endMs > item.startMs)) {
      setError('Фрагменты не должны пересекаться. Измените границы.');
      return;
    }
    const next = [...intervals, { startMs, endMs, label: `Фрагмент ${intervals.length + 1}` }].sort(
      (a, b) => a.startMs - b.startMs,
    );
    const nextTotal = next.reduce((sum, item) => sum + item.endMs - item.startMs, 0);
    if (nextTotal > MAX_TOTAL_MS) {
      setError('Общая выбранная длительность не должна превышать 20 минут.');
      return;
    }
    setIntervals(next);
  };

  const useWholeVideo = () => {
    if (!durationMs) return;
    if (durationMs > MAX_TOTAL_MS) {
      setError('Видео длиннее 20 минут: выберите только полезные участки.');
      return;
    }
    setIntervals([{ startMs: 0, endMs: durationMs, label: 'Весь материал' }]);
    setError(null);
  };

  const submit = () => {
    if (intervals.length === 0) {
      setError('Добавьте хотя бы один фрагмент на временной шкале.');
      return;
    }
    onSubmit(intervals, deleteSource);
  };

  return (
    <div className="clip-editor">
      <div className="clip-editor__head">
        <div>
          <p className="eyebrow">Шаг 2 из 2</p>
          <h2>Оставьте только полезные участки</h2>
          <p className="muted text-sm">
            В анализ и хранилище попадут выбранные фрагменты. Исходное длинное видео можно удалить сразу после нарезки.
          </p>
        </div>
        <span className="badge badge--neutral">H.264 · CRF 17 · ≤1080p</span>
      </div>

      <div className="clip-editor__workspace">
        <div>
          <video
            ref={videoRef}
            className="clip-editor__video"
            src={videoUrl}
            controls
            playsInline
            preload="metadata"
            onLoadedMetadata={(event) => {
              const measured = Math.round(event.currentTarget.duration * 1000);
              if (Number.isFinite(measured) && measured > 0) {
                setDurationMs(measured);
                setDraftEndMs((value) => (value > 0 ? Math.min(value, measured) : Math.min(30_000, measured)));
              }
            }}
            onTimeUpdate={(event) => setCurrentMs(Math.round(event.currentTarget.currentTime * 1000))}
          />

          <div
            className="clip-editor__timeline"
            role="slider"
            tabIndex={0}
            aria-label="Временная шкала исходного видео"
            aria-valuemin={0}
            aria-valuemax={durationMs}
            aria-valuenow={currentMs}
            onClick={(event) => {
              if (!durationMs) return;
              const rect = event.currentTarget.getBoundingClientRect();
              seek(((event.clientX - rect.left) / rect.width) * durationMs);
            }}
            onKeyDown={(event) => {
              if (event.key === 'ArrowLeft') seek(currentMs - 500);
              if (event.key === 'ArrowRight') seek(currentMs + 500);
            }}
          >
            {intervals.map((item, index) => (
              <div
                key={`${item.startMs}-${item.endMs}`}
                className="clip-editor__selection"
                style={{
                  left: `${(item.startMs / Math.max(durationMs, 1)) * 100}%`,
                  width: `${((item.endMs - item.startMs) / Math.max(durationMs, 1)) * 100}%`,
                }}
                title={`${index + 1}: ${formatTime(item.startMs)}–${formatTime(item.endMs)}`}
              />
            ))}
            <div
              className="clip-editor__playhead"
              style={{ left: `${(currentMs / Math.max(durationMs, 1)) * 100}%` }}
            />
          </div>
          <div className="row row--between text-xs muted mt-1">
            <span>{formatTime(0)}</span>
            <span>{formatTime(currentMs)} / {formatTime(durationMs)}</span>
            <span>{formatTime(durationMs)}</span>
          </div>
        </div>

        <aside className="clip-editor__aside">
          <div className="clip-editor__range-card">
            <div className="row row--between">
              <strong>Новый фрагмент</strong>
              <button type="button" className="btn btn--ghost text-xs" onClick={useWholeVideo}>
                Выбрать всё
              </button>
            </div>
            <div className="field mt-2">
              <label>Начало · {formatTime(draftStartMs)}</label>
              <input
                type="range"
                min={0}
                max={Math.max(durationMs, 1)}
                step={100}
                value={draftStartMs}
                onChange={(event) => setDraftStartMs(Math.min(Number(event.target.value), draftEndMs - MIN_INTERVAL_MS))}
              />
              <button type="button" className="btn btn--secondary btn--sm" onClick={() => setDraftStartMs(Math.min(currentMs, draftEndMs - MIN_INTERVAL_MS))}>
                Начало = текущий кадр
              </button>
            </div>
            <div className="field mt-2">
              <label>Конец · {formatTime(draftEndMs)}</label>
              <input
                type="range"
                min={0}
                max={Math.max(durationMs, 1)}
                step={100}
                value={draftEndMs}
                onChange={(event) => setDraftEndMs(Math.max(Number(event.target.value), draftStartMs + MIN_INTERVAL_MS))}
              />
              <button type="button" className="btn btn--secondary btn--sm" onClick={() => setDraftEndMs(Math.max(currentMs, draftStartMs + MIN_INTERVAL_MS))}>
                Конец = текущий кадр
              </button>
            </div>
            <button type="button" className="btn btn--full mt-2" onClick={addInterval}>
              + Добавить участок
            </button>
          </div>

          <div className="clip-editor__list" aria-live="polite">
            {intervals.length === 0 ? (
              <div className="empty clip-editor__empty">
                <div className="empty__title">Участки не выбраны</div>
                <span className="text-xs">Задайте начало и конец выше.</span>
              </div>
            ) : (
              intervals.map((item, index) => (
                <div className="clip-editor__item" key={`${item.startMs}-${item.endMs}`}>
                  <button type="button" className="clip-editor__play" onClick={() => seek(item.startMs)} aria-label={`Перейти к фрагменту ${index + 1}`}>
                    ▶
                  </button>
                  <div>
                    <strong>{item.label}</strong>
                    <small>{formatTime(item.startMs)}–{formatTime(item.endMs)} · {formatTime(item.endMs - item.startMs)}</small>
                  </div>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => setIntervals((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                    aria-label={`Удалить фрагмент ${index + 1}`}
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>

      {error && <div className="error mt-2">{error}</div>}

      <div className="clip-editor__footer">
        <label className="clip-editor__retention">
          <input type="checkbox" checked={deleteSource} onChange={(event) => setDeleteSource(event.target.checked)} />
          <span>
            <strong>Удалить исходное длинное видео после нарезки</strong>
            <small>
              Рекомендуется · исходник {sourceSizeBytes ? `${(sourceSizeBytes / 1024 / 1024).toFixed(1)} MB` : ''}, останутся только выбранные фрагменты.
            </small>
          </span>
        </label>
        <div className="row gap-2">
          <span className="muted text-xs">{intervals.length} фрагм. · {formatTime(totalMs)}</span>
          <button type="button" className="btn btn--secondary" onClick={onBack} disabled={busy}>
            Назад
          </button>
          <button type="button" className="btn" onClick={submit} disabled={busy || intervals.length === 0}>
            {busy ? 'Нарезаем и сжимаем…' : `Нарезать и запустить ${intervals.length || ''}`}
          </button>
        </div>
      </div>
    </div>
  );
}
