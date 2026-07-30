import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth, useToasts } from '../stores/auth';
import { formatRelative } from '../lib/format';

export function SubjectsPage() {
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();
  const hasRole = useAuth((s) => s.hasRole);
  const { data, isLoading, error } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.listSubjects(),
  });
  const [showNew, setShowNew] = useState(false);

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Субъекты</p>
          <h1>Заявленные люди</h1>
          <p>Профили людей, по которым создаются baseline-шаблоны слов.</p>
        </div>
        {hasRole('operator', 'system_admin') && (
          <button className="btn" onClick={() => setShowNew(true)}>
            + Новый субъект
          </button>
        )}
      </header>

      {isLoading ? (
        <div className="empty">Загрузка…</div>
      ) : error ? (
        <div className="empty">Ошибка</div>
      ) : !data || data.length === 0 ? (
        <div className="empty">
          <div className="empty__title">Субъектов пока нет</div>
          <button className="btn mt-2" onClick={() => setShowNew(true)}>
            + Создать первого
          </button>
        </div>
      ) : (
        <article className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Субъект</th>
                  <th>Согласие</th>
                  <th>Анализов</th>
                  <th>Шаблонов</th>
                  <th>Обновлён</th>
                </tr>
              </thead>
              <tbody>
                {data.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <Link to={`/subjects/${s.id}`} style={{ fontWeight: 600 }}>
                        {s.displayName || s.externalId}
                      </Link>
                      <small className="mono">{s.externalId}</small>
                    </td>
                    <td>
                      <StatusBadge value={s.consentState} />
                    </td>
                    <td>{s.nJobs}</td>
                    <td>{s.nBaselines}</td>
                    <td>
                      <small>{formatRelative(s.lastAnalyzedAt ?? s.createdAt)}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {showNew && (
        <NewSubjectDialog
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false);
            push({ message: 'Субъект создан', kind: 'success' });
            qc.invalidateQueries({ queryKey: ['subjects'] });
          }}
        />
      )}
    </>
  );
}

function NewSubjectDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [externalId, setExternalId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      await api.createSubject({ externalId, displayName, consentState: 'PENDING' });
      onCreated();
    } catch (e: any) {
      setErr(e.message || 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'grid', placeItems: 'center', zIndex: 100 }}
      onClick={onClose}
    >
      <form className="card" style={{ padding: 24, width: 420 }} onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="row row--between" style={{ marginBottom: 12 }}>
          <h2>Новый субъект</h2>
          <button type="button" className="btn btn--ghost" onClick={onClose}>✕</button>
        </div>
        <div className="form">
          <div className="field">
            <label>Внешний ID</label>
            <input className="input" value={externalId} onChange={(e) => setExternalId(e.target.value)} required />
          </div>
          <div className="field">
            <label>Отображаемое имя</label>
            <input className="input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>
          {err && <div className="error">{err}</div>}
          <div className="row gap-2" style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn--secondary" onClick={onClose}>Отмена</button>
            <button type="submit" className="btn" disabled={loading}>
              {loading ? 'Создание…' : 'Создать'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
