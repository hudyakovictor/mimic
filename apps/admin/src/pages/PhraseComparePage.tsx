import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { SyncPlayer, type SyncTrack, type Marker } from '../components/SyncPlayer';
import { fetchLandmarks } from '../lib/landmarks';
import { useToasts } from '../stores/auth';

export function PhraseComparePage() {
  const { word = '' } = useParams<{ word: string }>();
  const [params] = useSearchParams();
  const language = params.get('lang') ?? 'en';
  const push = useToasts((s) => s.push);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [tracks, setTracks] = useState<SyncTrack[]>([]);
  const [markers, setMarkers] = useState<Marker[]>([]);

  const decoded = decodeURIComponent(word);
  const { data: samples = [] } = useQuery({
    queryKey: ['samples-compare', decoded, language],
    queryFn: () => api.listSamplesForWord(decoded, language),
  });

  useEffect(() => {
    if (samples.length > 0 && selected.size === 0) {
      // Default: select first 3
      const s = new Set(samples.slice(0, 3).map((x) => x.id));
      setSelected(s);
    }
  }, [samples, selected.size]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const chosen = samples.filter((s) => selected.has(s.id));
      const newTracks: SyncTrack[] = [];
      let earliest = Number.POSITIVE_INFINITY;
      let latest = 0;
      for (const s of chosen) {
        try {
          const u = await api.getSampleUrls(decoded, s.id);
          let landmarks: { points: Float32Array; confidence: number }[] | null = null;
          if (!u.videoClipUrl && u.landmarksUrl) {
            const loaded = await fetchLandmarks(u.landmarksUrl);
            landmarks = loaded.points.map((p, i) => ({ points: p, confidence: loaded.confidences[i] }));
          }
          earliest = Math.min(earliest, s.startMs);
          latest = Math.max(latest, s.endMs);
          newTracks.push({
            id: s.id,
            videoUrl: u.videoClipUrl || u.landmarksUrl,
            landmarks,
            startMs: 0,
            endMs: Math.max(500, s.endMs - s.startMs),
            label: `${decoded} #${s.id.slice(0, 6)}`,
          });
        } catch (e) {
          // skip
        }
      }
      if (!cancelled) {
        // Normalize start times to 0 for sync
        newTracks.forEach((t) => {
          t.startMs = 0;
        });
        setTracks(newTracks);
        setMarkers([{ timeMs: 0, label: decoded }]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected, samples, decoded]);

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else if (next.size < 4) next.add(id);
    else push({ message: 'Максимум 4 дорожки', kind: 'info' });
    setSelected(next);
  };

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to="/words">Слова</Link> /{' '}
            <Link to={`/words/${word}?lang=${language}`}>{decoded}</Link> / Сравнение
          </p>
          <h1>Сравнение прогонов: {decoded}</h1>
          <p>Выберите до 4 verified-прогонов для синхронного просмотра.</p>
        </div>
        <div className="row gap-2">
          <span className="badge badge--neutral">
            {tracks.length} / 4 дорожек
          </span>
        </div>
      </header>

      <div className="grid grid--2">
        <article className="panel">
          <div className="panel__head">
            <h2>Выбор прогонов</h2>
            <p>{samples.length} доступно</p>
          </div>
          <div className="table-wrap" style={{ maxHeight: 360, overflow: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }}></th>
                  <th>ID</th>
                  <th>Время</th>
                  <th>Кадров</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => toggle(s.id)}
                    style={{ cursor: 'pointer', background: selected.has(s.id) ? 'var(--info-bg)' : undefined }}
                  >
                    <td>
                      <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
                    </td>
                    <td className="mono text-xs">{s.id.slice(0, 8)}</td>
                    <td className="text-sm muted">
                      {(s.endMs - s.startMs).toFixed(0)} ms
                    </td>
                    <td>{s.nFrames}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panel__head">
            <h2>Синхронизированный просмотр</h2>
            <p>Landmarks overlay</p>
          </div>
          <div className="panel__body">
            {tracks.length === 0 ? (
              <div className="empty">Выберите 1–4 прогона слева</div>
            ) : (
              <SyncPlayer tracks={tracks} markers={markers} height={420} />
            )}
          </div>
        </article>
      </div>
    </>
  );
}
