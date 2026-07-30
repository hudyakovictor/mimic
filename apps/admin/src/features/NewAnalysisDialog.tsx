// New analysis dialog: 3 modes (file upload, direct URL, YouTube URL)
// On success: poll import task until asset READY, then create job.

import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import { useToasts } from '../stores/auth';
import type { AnalysisJob, Asset } from '../types';

type Mode = 'upload' | 'url' | 'youtube';

export function NewAnalysisDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (job: AnalysisJob) => void;
}) {
  const [mode, setMode] = useState<Mode>('upload');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [phase, setPhase] = useState<'compose' | 'uploading' | 'importing' | 'ready' | 'failed'>('compose');
  const [progress, setProgress] = useState(0);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();

  const { data: subjects = [] } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.listSubjects(),
  });

  useEffect(() => {
    if (subjects.length > 0 && !subjectId) setSubjectId(subjects[0].id);
  }, [subjects, subjectId]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrMsg(null);
    if (!subjectId) {
      setErrMsg('Выберите субъекта');
      return;
    }
    try {
      let asset: Asset;
      if (mode === 'upload') {
        if (!file) {
          setErrMsg('Выберите файл');
          return;
        }
        setPhase('uploading');
        const prep = await api.prepareUpload({
          filename: file.name,
          mime: file.type || 'video/mp4',
          sizeBytes: file.size,
          title: title || file.name,
        });
        // Direct PUT to S3
        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.upload.addEventListener('progress', (ev) => {
            if (ev.lengthComputable) setProgress(ev.loaded / ev.total);
          });
          xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) resolve();
            else reject(new Error(`Upload failed: ${xhr.status}`));
          });
          xhr.addEventListener('error', () => reject(new Error('Network error')));
          const fd = new FormData();
          Object.entries(prep.fields).forEach(([k, v]) => fd.append(k, v));
          fd.append('file', file);
          xhr.open('PUT', prep.uploadUrl);
          xhr.send(fd);
        });
        // Compute SHA-256
        setProgress(1);
        const buf = await file.arrayBuffer();
        const hash = await crypto.subtle.digest('SHA-256', buf);
        const sha = Array.from(new Uint8Array(hash))
          .map((b) => b.toString(16).padStart(2, '0'))
          .join('');
        asset = await api.completeUpload(prep.assetId, { sha256: sha, hasAudio: true });
        setPhase('ready');
        push({ message: 'Видео загружено', kind: 'success' });
      } else {
        setPhase('importing');
        const result = await api.importFromUrl(url, title || undefined);
        if (!result.assetId) {
          throw new Error(result.error || 'Импорт не удался');
        }
        // Poll until READY
        let attempts = 0;
        while (attempts < 60) {
          await new Promise((r) => setTimeout(r, 2000));
          const list = await api.listAssets();
          const a = list.find((x) => x.id === result.assetId);
          if (a?.state === 'READY') {
            asset = a;
            break;
          }
          if (a?.state === 'FAILED') {
            throw new Error(a.failureReason || 'Импорт не удался');
          }
          attempts++;
        }
        if (!asset!) {
          throw new Error('Импорт занимает слишком долго');
        }
        setPhase('ready');
        push({ message: 'Видео импортировано', kind: 'success' });
      }

      // Create job
      const job = await api.createJob({ assetId: asset!.id, claimedPersonId: subjectId });
      qc.invalidateQueries({ queryKey: ['jobs'] });
      onCreated(job);
    } catch (e) {
      const err = e as ApiError | Error;
      setErrMsg((err as Error).message || 'Ошибка');
      setPhase('failed');
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Новый анализ"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'grid',
        placeItems: 'center',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <form
        className="card"
        style={{ padding: 24, width: 520, maxWidth: '92vw' }}
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <div className="row row--between" style={{ marginBottom: 12 }}>
          <h2>Новый анализ</h2>
          <button type="button" className="btn btn--ghost" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>

        <div className="filter-bar">
          {(['upload', 'url', 'youtube'] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={`btn ${mode === m ? '' : 'btn--secondary'} btn--sm`}
              onClick={() => setMode(m)}
            >
              {m === 'upload' ? 'Файл' : m === 'url' ? 'Ссылка' : 'YouTube'}
            </button>
          ))}
        </div>

        {mode === 'upload' ? (
          <div className="field">
            <label>Видео файл</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            {file && (
              <small className="muted">
                {file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB
              </small>
            )}
          </div>
        ) : (
          <div className="field">
            <label>{mode === 'youtube' ? 'YouTube URL' : 'Прямая ссылка на mp4'}</label>
            <input
              className="input"
              type="url"
              placeholder={mode === 'youtube' ? 'https://youtu.be/…' : 'https://example.com/video.mp4'}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          </div>
        )}

        <div className="field">
          <label>Название (опционально)</label>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>

        <div className="field">
          <label>Субъект</label>
          <select className="select" value={subjectId} onChange={(e) => setSubjectId(e.target.value)} required>
            <option value="">— выберите —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.displayName || s.externalId} · {s.consentState}
              </option>
            ))}
          </select>
          {subjects.length === 0 && (
            <small className="error">
              Сначала создайте субъекта и получите согласие. <a href="/subjects">Открыть</a>
            </small>
          )}
        </div>

        {phase === 'uploading' && (
          <div className="mt-2">
            <small className="muted">Загрузка: {Math.round(progress * 100)}%</small>
            <div style={{ height: 4, background: 'var(--surface-2)', borderRadius: 2, marginTop: 4 }}>
              <div
                style={{
                  width: `${progress * 100}%`,
                  height: '100%',
                  background: 'var(--accent)',
                  borderRadius: 2,
                  transition: 'width 0.2s',
                }}
              />
            </div>
          </div>
        )}
        {phase === 'importing' && (
          <small className="muted mt-2">Импортируем видео (это может занять несколько минут)…</small>
        )}

        {errMsg && <div className="error mt-2">{errMsg}</div>}

        <div className="row gap-2 mt-3" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Отмена
          </button>
          <button
            type="submit"
            className="btn"
            disabled={phase === 'uploading' || phase === 'importing'}
          >
            {phase === 'uploading'
              ? 'Загрузка…'
              : phase === 'importing'
              ? 'Импорт…'
              : 'Создать анализ'}
          </button>
        </div>
      </form>
    </div>
  );
}
