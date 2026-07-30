import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useToasts } from '../stores/auth';
import { formatPercent, formatRelative } from '../lib/format';
import { NewAnalysisDialog } from '../features/NewAnalysisDialog';

const STATES = ['', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'INSUFFICIENT_DATA'];

export function AnalysesPage() {
  const [state, setState] = useState<string>('');
  const [showNew, setShowNew] = useState(false);
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs', { state }],
    queryFn: () => api.listJobs({ state: state || undefined, limit: 100 }),
  });

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Очередь</p>
          <h1>Анализы</h1>
          <p>Все запущенные и завершённые задачи пайплайна.</p>
        </div>
        <div className="row gap-2">
          <button className="btn" onClick={() => setShowNew(true)}>
            + Новый анализ
          </button>
        </div>
      </header>

      <div className="filter-bar">
        <span className="text-sm muted">Состояние:</span>
        <select className="select" value={state} onChange={(e) => setState(e.target.value)}>
          {STATES.map((s) => (
            <option key={s} value={s}>
              {s || 'Все'}
            </option>
          ))}
        </select>
        <span className="spacer" />
        <button className="btn btn--secondary btn--sm" onClick={() => refetch()}>
          Обновить
        </button>
      </div>

      {isLoading ? (
        <div className="empty">
          <div className="empty__title">Загрузка…</div>
        </div>
      ) : error ? (
        <div className="empty">
          <div className="empty__title">Ошибка</div>
          <button className="btn mt-2" onClick={() => refetch()}>
            Повторить
          </button>
        </div>
      ) : !data || data.length === 0 ? (
        <div className="empty">
          <div className="empty__title">Анализов пока нет</div>
          <p>Создайте первый анализ, нажав «Новый анализ».</p>
          <button className="btn mt-2" onClick={() => setShowNew(true)}>
            + Новый анализ
          </button>
        </div>
      ) : (
        <article className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Анализ</th>
                  <th>Субъект</th>
                  <th>Состояние</th>
                  <th>Риск</th>
                  <th>Качество</th>
                  <th>Создан</th>
                </tr>
              </thead>
              <tbody>
                {data.map((j) => (
                  <tr key={j.id}>
                    <td>
                      <Link to={`/analyses/${j.id}`} style={{ fontWeight: 600 }}>
                        {j.id.slice(0, 8)}
                      </Link>
                      <small>
                        {j.attempt > 1 && `попытка ${j.attempt} · `}
                        {j.lastError ? j.lastError.slice(0, 60) : '—'}
                      </small>
                    </td>
                    <td className="mono text-xs">{j.subjectId.slice(0, 8)}</td>
                    <td>
                      <StatusBadge value={j.decision?.label ?? j.state} />
                    </td>
                    <td>{j.decision ? formatPercent(j.decision.riskScore) : '—'}</td>
                    <td>{j.decision ? formatPercent(j.decision.qualityScore) : '—'}</td>
                    <td>
                      <small>{formatRelative(j.createdAt)}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {showNew && (
        <NewAnalysisDialog
          onClose={() => setShowNew(false)}
          onCreated={(job) => {
            setShowNew(false);
            push({ message: 'Анализ создан', kind: 'success' });
            qc.invalidateQueries({ queryKey: ['jobs'] });
            window.location.assign(`/analyses/${job.id}`);
          }}
        />
      )}
    </>
  );
}
