import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth, useToasts } from '../stores/auth';
import { formatDate, formatRelative } from '../lib/format';
import { useState } from 'react';

export function SubjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();
  const hasRole = useAuth((s) => s.hasRole);
  const { data } = useQuery({
    queryKey: ['subject', id],
    queryFn: () => api.getSubject(id!),
    enabled: !!id,
  });
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs', { subjectId: id }],
    queryFn: () => api.listJobs({ subjectId: id, limit: 20 }),
    enabled: !!id,
  });
  const [consentForm, setConsentForm] = useState<{ state: string; signedBy: string } | null>(null);

  if (!data) return <div className="empty">Загрузка…</div>;

  const recordConsent = async () => {
    if (!consentForm) return;
    try {
      await api.updateSubject(data.id, {
        consentState: consentForm.state,
        version: data.version,
      });
      await api.recordConsent(data.id, { state: consentForm.state, signedBy: consentForm.signedBy });
      push({ message: 'Согласие записано', kind: 'success' });
      setConsentForm(null);
      qc.invalidateQueries({ queryKey: ['subject', id] });
    } catch (e: any) {
      push({ message: e.message, kind: 'error' });
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to="/subjects">Субъекты</Link> / {data.displayName || data.externalId}
          </p>
          <h1>{data.displayName || data.externalId}</h1>
          <p className="muted text-sm">ID: <span className="mono">{data.id}</span></p>
        </div>
        <div className="row gap-2">
          <StatusBadge value={data.consentState} />
          {hasRole('operator', 'system_admin') && (
            <button className="btn btn--secondary" onClick={() => setConsentForm({ state: 'GRANTED', signedBy: '' })}>
              Записать согласие
            </button>
          )}
        </div>
      </header>

      <div className="grid grid--2">
        <article className="panel">
          <div className="panel__head">
            <h2>Профиль</h2>
          </div>
          <div className="panel__body">
            <div className="row row--between"><span className="muted">External ID</span><span className="mono">{data.externalId}</span></div>
            <div className="row row--between"><span className="muted">Согласие</span><StatusBadge value={data.consentState} /></div>
            <div className="row row--between"><span className="muted">Анализов</span><span>{data.nJobs}</span></div>
            <div className="row row--between"><span className="muted">Шаблонов</span><span>{data.nBaselines}</span></div>
            <div className="row row--between"><span className="muted">Последний анализ</span><span>{formatDate(data.lastAnalyzedAt)}</span></div>
            <div className="row row--between"><span className="muted">Создан</span><span>{formatDate(data.createdAt)}</span></div>
          </div>
        </article>

        <article className="panel">
          <div className="panel__head">
            <h2>Последние анализы</h2>
            <p>{jobs.length}</p>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Статус</th><th>Когда</th></tr></thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td>
                      <Link to={`/analyses/${j.id}`} className="mono text-xs">{j.id.slice(0, 8)}</Link>
                    </td>
                    <td><StatusBadge value={j.decision?.label ?? j.state} /></td>
                    <td><small>{formatRelative(j.createdAt)}</small></td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr><td colSpan={3} className="muted text-sm" style={{ textAlign: 'center', padding: 12 }}>Нет анализов</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </article>
      </div>

      {consentForm && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'grid', placeItems: 'center', zIndex: 100 }}
          onClick={() => setConsentForm(null)}
        >
          <div className="card" style={{ padding: 24, width: 380 }} onClick={(e) => e.stopPropagation()}>
            <h2 className="mt-0">Согласие субъекта</h2>
            <div className="form">
              <div className="field">
                <label>Состояние</label>
                <select className="select" value={consentForm.state} onChange={(e) => setConsentForm({ ...consentForm, state: e.target.value })}>
                  <option value="GRANTED">Дано (GRANTED)</option>
                  <option value="REVOKED">Отозвано (REVOKED)</option>
                  <option value="PENDING">Ожидает (PENDING)</option>
                </select>
              </div>
              <div className="field">
                <label>Подписал</label>
                <input className="input" value={consentForm.signedBy} onChange={(e) => setConsentForm({ ...consentForm, signedBy: e.target.value })} />
              </div>
              <div className="row gap-2" style={{ justifyContent: 'flex-end' }}>
                <button className="btn btn--secondary" onClick={() => setConsentForm(null)}>Отмена</button>
                <button className="btn" onClick={recordConsent}>Записать</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
