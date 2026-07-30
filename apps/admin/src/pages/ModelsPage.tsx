import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { formatDate } from '../lib/format';
import { useState } from 'react';

export function ModelsPage() {
  const [kind, setKind] = useState('');
  const { data, isLoading, error } = useQuery({
    queryKey: ['models', { kind }],
    queryFn: () => api.listModels({ kind: kind || undefined }),
  });

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Registry</p>
          <h1>Модели</h1>
          <p>Версии scorer'ов и адаптеров. Только ACTIVE используется в production scoring.</p>
        </div>
      </header>

      <div className="filter-bar">
        <span className="text-sm muted">Тип:</span>
        <select className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">Все</option>
          <option value="LANDMARK_EXTRACTOR">Landmark extractor</option>
          <option value="ASR">ASR</option>
          <option value="MOTION_SCORER">Motion scorer</option>
          <option value="CALIBRATION">Calibration</option>
        </select>
      </div>

      {isLoading ? (
        <div className="empty">Загрузка…</div>
      ) : error ? (
        <div className="empty">Ошибка</div>
      ) : !data || data.length === 0 ? (
        <div className="empty">Моделей пока нет</div>
      ) : (
        <article className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Тип</th>
                  <th>Версия</th>
                  <th>Состояние</th>
                  <th>Checksum</th>
                  <th>Создана</th>
                </tr>
              </thead>
              <tbody>
                {data.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <Link to={`/models/${m.id}`}>{m.kind}</Link>
                    </td>
                    <td className="mono">{m.version}</td>
                    <td><StatusBadge value={m.state} /></td>
                    <td className="mono text-xs">{m.artifactChecksum.slice(0, 12)}…</td>
                    <td><small>{formatDate(m.createdAt)}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}
    </>
  );
}
