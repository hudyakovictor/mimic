import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { formatRelative } from '../lib/format';
import { useState } from 'react';

export function ReviewsPage() {
  const [verdict, setVerdict] = useState('');
  const { data, isLoading, error } = useQuery({
    queryKey: ['reviews', { verdict }],
    queryFn: () => api.listReviews({ verdict: verdict || undefined, limit: 100 }),
  });

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Проверки</p>
          <h1>Ревью решений</h1>
          <p>Все ревью, оставленные ревьюерами по решениям модели.</p>
        </div>
      </header>

      <div className="filter-bar">
        <span className="text-sm muted">Вердикт:</span>
        <select className="select" value={verdict} onChange={(e) => setVerdict(e.target.value)}>
          <option value="">Все</option>
          <option value="CONFIRMED_GENUINE">Подтверждено</option>
          <option value="CONFIRMED_SUSPICIOUS">Подтверждено подозрение</option>
          <option value="UNDECIDABLE">Не решено</option>
        </select>
      </div>

      {isLoading ? (
        <div className="empty">Загрузка…</div>
      ) : error ? (
        <div className="empty">Ошибка</div>
      ) : !data || data.length === 0 ? (
        <div className="empty">
          <div className="empty__title">Ревью пока нет</div>
        </div>
      ) : (
        <article className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ревью</th>
                  <th>Decision</th>
                  <th>Ревьюер</th>
                  <th>Вердикт</th>
                  <th>Когда</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link to={`/reviews/${r.id}`} className="mono text-xs">{r.id.slice(0, 8)}</Link>
                    </td>
                    <td>
                      <Link to={`/analyses/${r.decisionId}`} className="mono text-xs">
                        {r.decisionId.slice(0, 8)}
                      </Link>
                    </td>
                    <td>{r.reviewerName || r.reviewerId.slice(0, 8)}</td>
                    <td>
                      <StatusBadge value={r.verdict} />
                    </td>
                    <td>
                      <small>{formatRelative(r.createdAt)}</small>
                    </td>
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
