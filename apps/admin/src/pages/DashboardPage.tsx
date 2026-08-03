import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Metric } from '../components/Metric';
import { StatusBadge } from '../components/StatusBadge';
import { formatPercent, formatRelative } from '../lib/format';

export function DashboardPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: () => api.dashboardMetrics(),
  });

  if (isLoading) {
    return (
      <>
        <header className="page-head">
          <div>
            <p className="eyebrow">Контроль анализа</p>
            <h1>Обзор системы</h1>
          </div>
        </header>
        <div className="metrics">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="metric">
              <div className="skeleton" style={{ width: '40%' }} />
              <div className="skeleton" style={{ width: '60%', marginTop: 8, height: 24 }} />
              <div className="skeleton" style={{ width: '80%', marginTop: 6 }} />
            </div>
          ))}
        </div>
      </>
    );
  }
  if (error) {
    return (
      <div className="empty">
        <div className="empty__title">Не удалось загрузить метрики</div>
        <button className="btn mt-2" onClick={() => refetch()}>
          Повторить
        </button>
      </div>
    );
  }
  if (!data) return null;

  const m = data;
  const max = Math.max(1, ...m.jobsLast7D.map((d) => d.count));
  const median = m.medianProcessingSeconds
    ? m.medianProcessingSeconds < 60
      ? `${Math.round(m.medianProcessingSeconds)} сек`
      : `${Math.round(m.medianProcessingSeconds / 60)} мин`
    : '—';

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Контроль анализа</p>
          <h1>Обзор системы</h1>
          <p>
            Решения по динамике ключевых точек лица, качеству трека и персональному эталону.{' '}
            {isFetching && <span className="muted text-xs">обновление…</span>}
          </p>
        </div>
        <div className="row gap-2">
          <Link to="/analyses" className="btn btn--secondary">
            Открыть очередь
          </Link>
          <Link to="/words" className="btn">
            База слов
          </Link>
        </div>
      </header>

      <section className="metrics" aria-label="Ключевые метрики">
        <Metric
          label="Требуют проверки"
          value={m.pendingReviews}
          detail="ожидают ревью"
          tone={m.pendingReviews > 0 ? 'risk' : 'good'}
        />
        <Metric
          label="Достаточное качество"
          value={formatPercent(m.qualityOkRatio)}
          detail="за 7 дней"
          tone={m.qualityOkRatio >= 0.8 ? 'good' : 'info'}
        />
        <Metric label="Медиана обработки" value={median} detail="p50 за 7 дней" />
        <Metric
          label="Согласие ревьюеров"
          value={formatPercent(m.reviewerAgreement)}
          detail="Cohen's κ (приближ.)"
          tone={m.reviewerAgreement >= 0.8 ? 'good' : 'info'}
        />
      </section>

      <section className="grid grid--main mt-3">
        <article className="panel">
          <div className="panel__head">
            <div>
              <h2>Активность за 7 дней</h2>
              <p>Количество анализов и доля подозрительных</p>
            </div>
          </div>
          <div className="panel__body">
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 160 }}>
              {m.jobsLast7D.length === 0 ? (
                <div className="empty" style={{ flex: 1 }}>
                  <div className="empty__title">Нет данных</div>
                </div>
              ) : (
                m.jobsLast7D.map((d) => (
                  <div key={d.date} style={{ flex: 1, display: 'grid', placeItems: 'center' }}>
                    <div
                      style={{
                        width: '70%',
                        background: 'var(--surface-2)',
                        height: `${(d.count / max) * 100}%`,
                        position: 'relative',
                        borderRadius: '4px 4px 0 0',
                        minHeight: 4,
                      }}
                      title={`${d.date}: ${d.count} jobs, ${d.suspicious} suspicious`}
                    >
                      {d.suspicious > 0 && (
                        <div
                          style={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            right: 0,
                            height: `${(d.suspicious / d.count) * 100}%`,
                            background: 'var(--danger)',
                            borderRadius: '4px 4px 0 0',
                          }}
                        />
                      )}
                    </div>
                    <div className="text-xs muted" style={{ marginTop: 4 }}>
                      {d.date.slice(5)}
                    </div>
                    <div className="text-xs">{d.count}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel__head">
            <div>
              <h2>Последние анализы</h2>
              <p>10 самых свежих</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Анализ</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {m.recentAnalyses.slice(0, 10).map((j) => (
                  <tr key={j.id}>
                    <td>
                      <Link to={`/analyses/${j.id}`} style={{ fontWeight: 600 }}>
                        {j.id.slice(0, 8)}
                      </Link>
                      <small>{formatRelative(j.createdAt)}</small>
                    </td>
                    <td>
                      <StatusBadge value={j.decision?.label ?? j.state} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </>
  );
}
