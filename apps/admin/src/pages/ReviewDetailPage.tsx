import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { formatDate } from '../lib/format';

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: reviews } = useQuery({
    queryKey: ['reviews', { decisionId: id }],
    queryFn: () => api.listReviews({ decisionId: id, limit: 50 }),
  });
  const r = reviews?.[0];

  if (!r) return <div className="empty">Загрузка…</div>;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to="/reviews">Ревью</Link> / {r.id.slice(0, 8)}
          </p>
          <h1>Ревью решения</h1>
        </div>
        <StatusBadge value={r.verdict} />
      </header>
      <article className="panel">
        <div className="panel__body">
          <div className="row row--between">
            <span className="muted">Решение</span>
            <Link to={`/analyses/${r.decisionId}`} className="mono text-xs">{r.decisionId}</Link>
          </div>
          <div className="row row--between">
            <span className="muted">Ревьюер</span>
            <span>{r.reviewerName || r.reviewerId}</span>
          </div>
          <div className="row row--between">
            <span className="muted">Уверенность</span>
            <span>{r.confidence != null ? r.confidence.toFixed(2) : '—'}</span>
          </div>
          <div className="row row--between">
            <span className="muted">Создано</span>
            <span>{formatDate(r.createdAt)}</span>
          </div>
          <h3 className="mt-3">Причина</h3>
          <div className="card" style={{ padding: 12 }}>
            {r.reason}
          </div>
        </div>
      </article>
    </>
  );
}
