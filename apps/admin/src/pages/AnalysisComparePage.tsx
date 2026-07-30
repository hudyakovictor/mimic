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

        // Probe video URL for the asset
        const urlRes = await fetch(`/api/v1/assets/${job.assetId}/downloadUrl`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
        });
        if (!urlRes.ok) throw new Error('Cannot get download URL');
        const { url } = await urlRes.json();
        newTracks.push({
          id: 'probe',
          videoUrl: url,
          startMs: 0,
          endMs: job.finishedAt && job.startedAt
            ? (new Date(job.finishedAt).getTime() - new Date(job.startedAt).getTime())
            : 60_000,
          label: 'Probe',
          color: '#ffffff',
        });

        // Add baseline samples for the first phrase
        const first = job.decision.phraseInstances[0];
        if (first) {
          const samples = await api.listSamplesForWord(first.word, first.language);
          const head = samples.slice(0, 3);
          for (const s of head) {
            try {
              const u = await api.getSampleUrls(first.word, s.id);
              // Try to fetch landmarks if no video clip
              let landmarks: { points: Float32Array; confidence: number }[] | null = null;
              if (!u.videoClipUrl && u.landmarksUrl) {
                const loaded = await fetchLandmarks(u.landmarksUrl);
                landmarks = loaded.points.map((p, i) => ({ points: p, confidence: loaded.confidences[i] }));
              }
              newTracks.push({
                id: s.id,
                videoUrl: u.videoClipUrl || u.landmarksUrl,
                landmarks,
                startMs: s.startMs,
                endMs: s.endMs,
                label: `${first.word} (n=${s.nFrames})`,
              });
            } catch (e) {
              // skip
            }
          }
        }

        // Markers
        for (const pi of job.decision.phraseInstances) {
          newMarkers.push({ timeMs: pi.startMs, label: pi.word });
        }

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
