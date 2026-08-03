import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import { useToasts } from '../stores/auth';
import type { AnalysisJob, Asset } from '../types';
import { ClipEditor, type SelectedInterval } from './ClipEditor';

type Mode = 'upload' | 'url' | 'youtube';
type Phase = 'compose' | 'uploading' | 'importing' | 'trim' | 'clipping' | 'failed';

export function NewAnalysisDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (jobs: AnalysisJob[]) => void;
}) {
  const [mode, setMode] = useState<Mode>('upload');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [phase, setPhase] = useState<Phase>('compose');
  const [progress, setProgress] = useState(0);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [sourceAsset, setSourceAsset] = useState<Asset | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const localPreviewRef = useRef<string | null>(null);
  const push = useToasts((state) => state.push);
  const queryClient = useQueryClient();

  const { data: subjects = [] } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.listSubjects(),
  });

  useEffect(() => {
    const firstGranted = subjects.find((subject) => subject.consentState === 'GRANTED');
    if (!subjectId && firstGranted) setSubjectId(firstGranted.id);
  }, [subjects, subjectId]);

  useEffect(
    () => () => {
      if (localPreviewRef.current) URL.revokeObjectURL(localPreviewRef.current);
    },
    [],
  );

  const showClipEditor = async (asset: Asset, localFile?: File) => {
    setSourceAsset(asset);
    if (localPreviewRef.current) URL.revokeObjectURL(localPreviewRef.current);
    if (localFile) {
      const objectUrl = URL.createObjectURL(localFile);
      localPreviewRef.current = objectUrl;
      setPreviewUrl(objectUrl);
    } else {
      const result = await api.getAssetDownloadUrl(asset.id);
      setPreviewUrl(result.url);
    }
    setPhase('trim');
  };

  const submitSource = async (event: React.FormEvent) => {
    event.preventDefault();
    setErrMsg(null);
    if (!subjectId) {
      setErrMsg('Выберите субъекта с подтверждённым согласием.');
      return;
    }
    try {
      let asset: Asset;
      if (mode === 'upload') {
        if (!file) {
          setErrMsg('Выберите видеофайл.');
          return;
        }
        setPhase('uploading');
        const prepared = await api.prepareUpload({
          filename: file.name,
          mime: file.type || 'video/mp4',
          sizeBytes: file.size,
          title: title || file.name,
        });
        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.upload.addEventListener('progress', (uploadEvent) => {
            if (uploadEvent.lengthComputable) setProgress(uploadEvent.loaded / uploadEvent.total);
          });
          xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) resolve();
            else reject(new Error(`S3 upload failed (${xhr.status})`));
          });
          xhr.addEventListener('error', () => reject(new Error('Сетевая ошибка при загрузке.')));
          const body = new FormData();
          Object.entries(prepared.fields).forEach(([key, value]) => body.append(key, value));
          if (!prepared.fields['Content-Type']) body.append('Content-Type', file.type || 'video/mp4');
          body.append('file', file);
          xhr.open('POST', prepared.uploadUrl);
          xhr.send(body);
        });
        setProgress(1);
        // The API streams the object to compute the authoritative SHA-256;
        // the browser never allocates a second copy of a potentially 1 GB file.
        asset = await api.completeUpload(prepared.assetId, { hasAudio: true });
        push({ message: 'Исходное видео загружено. Выберите участки.', kind: 'success' });
        await showClipEditor(asset, file);
      } else {
        if (!url) {
          setErrMsg('Укажите ссылку на видео.');
          return;
        }
        setPhase('importing');
        const imported = await api.importFromUrl(url, title || undefined);
        if (!imported.assetId) throw new Error(imported.error || 'Импорт не удался.');
        let attempts = 0;
        while (attempts < 150) {
          await new Promise((resolve) => window.setTimeout(resolve, 2_000));
          const current = await api.getAsset(imported.assetId);
          if (current.state === 'READY') {
            asset = current;
            break;
          }
          if (current.state === 'FAILED') {
            throw new Error(current.failureReason || 'Импорт не удался.');
          }
          attempts += 1;
        }
        if (!asset!) throw new Error('Импорт занимает слишком долго. Попробуйте позже.');
        push({ message: 'Видео импортировано. Выберите участки.', kind: 'success' });
        await showClipEditor(asset);
      }
    } catch (error) {
      const exception = error as ApiError | Error;
      setErrMsg(exception.message || 'Не удалось подготовить видео.');
      setPhase('failed');
    }
  };

  const createAnalyses = async (intervals: SelectedInterval[], deleteSource: boolean) => {
    if (!sourceAsset) return;
    setErrMsg(null);
    setPhase('clipping');
    try {
      const result = await api.createClips(sourceAsset.id, {
        intervals: intervals.map((interval) => ({
          startMs: interval.startMs,
          endMs: interval.endMs,
          label: interval.label,
        })),
        deleteSource,
      });
      // Independent clips enter the queue together; one slow fragment does not
      // delay registration of the others.
      const jobs = await Promise.all(
        result.clips.map((clip) =>
          api.createJob({ assetId: clip.id, claimedPersonId: subjectId }),
        ),
      );
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      push({
        message: `${jobs.length} ${jobs.length === 1 ? 'анализ создан' : 'анализа запущены параллельно'}`,
        kind: 'success',
      });
      onCreated(jobs);
    } catch (error) {
      const exception = error as ApiError | Error;
      setErrMsg(exception.message || 'Не удалось нарезать видео.');
      setPhase('trim');
    }
  };

  const busy = phase === 'uploading' || phase === 'importing' || phase === 'clipping';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Новый анализ"
      className="dialog-backdrop"
      onClick={() => !busy && onClose()}
    >
      {phase === 'trim' || phase === 'clipping' ? (
        <div className="card clip-editor-dialog" onClick={(event) => event.stopPropagation()}>
          <ClipEditor
            videoUrl={previewUrl}
            knownDurationMs={sourceAsset?.durationMs}
            sourceSizeBytes={sourceAsset?.sizeBytes}
            busy={phase === 'clipping'}
            onBack={() => setPhase('compose')}
            onSubmit={createAnalyses}
          />
          {errMsg && <div className="error mt-2">{errMsg}</div>}
        </div>
      ) : (
        <form className="card new-analysis" onClick={(event) => event.stopPropagation()} onSubmit={submitSource}>
          <div className="row row--between" style={{ marginBottom: 12 }}>
            <div>
              <p className="eyebrow">Шаг 1 из 2</p>
              <h2>Добавить видео</h2>
            </div>
            <button type="button" className="btn btn--ghost" onClick={onClose} aria-label="Закрыть">
              ✕
            </button>
          </div>

          <div className="source-tabs" role="tablist" aria-label="Источник видео">
            {(['upload', 'url', 'youtube'] as Mode[]).map((sourceMode) => (
              <button
                key={sourceMode}
                type="button"
                role="tab"
                aria-selected={mode === sourceMode}
                className={mode === sourceMode ? 'source-tab source-tab--active' : 'source-tab'}
                onClick={() => setMode(sourceMode)}
              >
                <span>{sourceMode === 'upload' ? '↑' : sourceMode === 'url' ? '↗' : '▶'}</span>
                {sourceMode === 'upload' ? 'Файл' : sourceMode === 'url' ? 'MP4-ссылка' : 'YouTube'}
              </button>
            ))}
          </div>

          {mode === 'upload' ? (
            <label className="upload-dropzone">
              <input
                type="file"
                accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <span className="upload-dropzone__icon">↑</span>
              <strong>{file ? file.name : 'Выберите видеофайл'}</strong>
              <small>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : 'MP4, MOV, WebM или MKV · до 1 GB'}</small>
            </label>
          ) : (
            <div className="field">
              <label>{mode === 'youtube' ? 'Ссылка YouTube' : 'Прямая HTTPS-ссылка на видео'}</label>
              <input
                className="input"
                type="url"
                placeholder={mode === 'youtube' ? 'https://youtu.be/…' : 'https://example.com/video.mp4'}
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                required
              />
            </div>
          )}

          <div className="grid grid--2">
            <div className="field">
              <label>Название</label>
              <input className="input" placeholder="Например, интервью 30 июля" value={title} onChange={(event) => setTitle(event.target.value)} />
            </div>
            <div className="field">
              <label>Заявленный человек</label>
              <select className="select" value={subjectId} onChange={(event) => setSubjectId(event.target.value)} required>
                <option value="">— выберите —</option>
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id} disabled={subject.consentState !== 'GRANTED'}>
                    {subject.displayName || subject.externalId} · {subject.consentState === 'GRANTED' ? 'согласие есть' : 'нет согласия'}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {phase === 'uploading' && (
            <div className="upload-progress">
              <div className="row row--between text-xs">
                <span>Загрузка исходника</span>
                <strong>{Math.round(progress * 100)}%</strong>
              </div>
              <div className="upload-progress__track"><div style={{ width: `${progress * 100}%` }} /></div>
            </div>
          )}
          {phase === 'importing' && <div className="notice mt-2">Импортируем и проверяем видео. YouTube может занять несколько минут…</div>}
          {errMsg && <div className="error mt-2">{errMsg}</div>}

          <div className="notice notice--storage mt-3">
            <strong>Экономия места включена</strong>
            <span>На следующем шаге вы выберете нужные участки. Они сохранятся в H.264 CRF 17 без заметного ущерба для анализа мимики; длинный исходник можно удалить.</span>
          </div>

          <div className="row gap-2 mt-3" style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn--secondary" onClick={onClose} disabled={busy}>Отмена</button>
            <button type="submit" className="btn" disabled={busy || !subjectId}>
              {phase === 'uploading' ? 'Загрузка…' : phase === 'importing' ? 'Импорт…' : phase === 'failed' ? 'Повторить' : 'Продолжить к выбору участков →'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
