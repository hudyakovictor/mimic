import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { SyncPlayer, type SyncTrack, type Marker } from '../components/SyncPlayer';
import { fetchLandmarks } from '../lib/landmarks';

export function AnalysisComparePage() {
  const { id } = useParams<{ id: string }>();
  const [tracks, setTracks] = useState<SyncTrack[]>([]);
  const [markers, setMarkers] = useState<Marker[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data: job } = useQuery({
    queryKey: ['job', id],
    queryFn: () => api.getJob(id!),
    enabled: !!id,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!job?.decision) return;
      try {
        setError(null);
        // Track 1: the asset of this job (original video)
        const newTracks: SyncTrack[] = [];
        const newMarkers: Marker[] = [];

        const first = job.decision.phraseInstances[0];
        const artifacts = await api.getJobArtifacts(job.id);
        let probeLandmarks: { points: Float32Array; confidence: number }[] | null = null;
        let probeLandmarkFps = artifacts.fps;
        if (artifacts.landmarksUrl) {
          const loaded = await fetchLandmarks(artifacts.landmarksUrl);
          probeLandmarkFps = loaded.fps;
          probeLandmarks = loaded.points.map((points, index) => ({
            points,
            confidence: loaded.confidences[index],
          }));
        }
        newTracks.push({
          id: 'probe',
          videoUrl: artifacts.videoUrl,
          landmarks: probeLandmarks,
          landmarkFps: probeLandmarkFps,
          startMs: first?.startMs ?? 0,
          endMs: first?.endMs ?? artifacts.durationMs,
          label: first ? `Проверяемое · «${first.word}»` : 'Проверяемое видео',
          color: '#ffffff',
        });

        // Add verified baseline samples for the first recognized phrase
        if (first) {
          const samples = await api.listSamplesForWord(
            first.word,
            first.language,
            undefined,
            undefined,
            job.subjectId,
          );
          const head = samples.slice(0, 3);
          for (const s of head) {
            try {
              const u = await api.getSampleUrls(first.word, s.id);
              let landmarks: { points: Float32Array; confidence: number }[] | null = null;
              let landmarkFps = 30;
              if (u.landmarksUrl) {
                const loaded = await fetchLandmarks(u.landmarksUrl);
                landmarkFps = loaded.fps;
                landmarks = loaded.points.map((points, index) => ({
                  points,
                  confidence: loaded.confidences[index],
                }));
              }
              newTracks.push({
                id: s.id,
                videoUrl: u.videoClipUrl,
                landmarks,
                landmarkFps,
                startMs: u.videoInPointMs,
                endMs: u.videoOutPointMs,
                label: `Эталон · «${first.word}» #${s.id.slice(0, 5)}`,
              });
            } catch {
              // skip
            }
          }
        }

        if (first) newMarkers.push({ timeMs: 0, label: first.word });

        if (!cancelled) {
          setTracks(newTracks);
          setMarkers(newMarkers);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Не удалось подготовить сравнение');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [job]);

  if (!job?.decision) {
    return (
      <div className="empty">
        <div className="empty__title">Решение не готово</div>
        <Link to={`/analyses/${id}`}>К анализу</Link>
      </div>
    );
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to={`/analyses/${id}`}>Анализ</Link> / Сравнение
          </p>
          <h1>Side-by-side сравнение</h1>
          <p>Оригинальное видео слева, baseline-прогоны справа. Синхронное воспроизведение.</p>
        </div>
        <div className="row gap-2">
          <span className="badge badge--neutral">{tracks.length} дорожек</span>
        </div>
      </header>

      {error && <div className="error mb-2">{error}</div>}

      {tracks.length === 0 ? (
        <div className="empty">
          <div className="empty__title">Готовим дорожки…</div>
        </div>
      ) : (
        <SyncPlayer tracks={tracks} markers={markers} height={540} autoPlay={false} />
      )}

      <div className="panel mt-3">
        <div className="panel__head">
          <h2>Подсказки</h2>
        </div>
        <div className="panel__body text-sm muted">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>Space — play/pause</li>
            <li>←/→ — перемотка на 1 секунду</li>
            <li>Клик по таймлайну — переход к моменту</li>
            <li>Синяя точка — распознанное слово; кликните, чтобы перейти</li>
          </ul>
        </div>
      </div>
    </>
  );
}
