import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth, useToasts } from '../stores/auth';
import { formatDate } from '../lib/format';

export function ModelDetailPage() {
  const { id } = useParams<{ id: string }>();
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();
  const hasRole = useAuth((s) => s.hasRole);
  const { data: m } = useQuery({
    queryKey: ['model', id],
    queryFn: () => api.getModel(id!),
    enabled: !!id,
  });
  const [reason, setReason] = useState('');
  const [targetState, setTargetState] = useState('');

  if (!m) return <div className="empty">Загрузка…</div>;

  const transitionStates: Record<string, string[]> = {
    DRAFT: ['VALIDATED', 'RETIRED'],
    VALIDATED: ['SHADOW', 'RETIRED'],
    SHADOW: ['ACTIVE', 'RETIRED'],
    ACTIVE: ['RETIRED'],
    RETIRED: [],
  };

  const promote = async () => {
    if (!targetState || reason.length < 10) {
      push({ message: 'Укажите целевое состояние и причину (10+ символов)', kind: 'error' });
      return;
    }
    try {
      await api.promoteModel(m.id, targetState, reason);
      push({ message: `Переведено в ${targetState}`, kind: 'success' });
      setReason('');
      setTargetState('');
      qc.invalidateQueries({ queryKey: ['model', id] });
      qc.invalidateQueries({ queryKey: ['models'] });
    } catch (e: any) {
      push({ message: e.message, kind: 'error' });
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to="/models">Модели</Link> / {m.kind}
          </p>
          <h1>
            {m.kind} <span className="mono muted text-sm">v{m.version}</span>
          </h1>
        </div>
        <StatusBadge value={m.state} />
      </header>

      <div className="grid grid--2">
        <article className="panel">
          <div className="panel__head"><h2>Метаданные</h2></div>
          <div className="panel__body">
            <div className="row row--between"><span className="muted">Checksum</span><span className="mono text-xs">{m.artifactChecksum}</span></div>
            <div className="row row--between"><span className="muted">Code commit</span><span className="mono text-xs">{m.codeCommit || '—'}</span></div>
            <div className="row row--between"><span className="muted">Feature schema</span><span className="mono text-xs">{m.featureSchema || '—'}</span></div>
            <div className="row row--between"><span className="muted">Создана</span><span>{formatDate(m.createdAt)}</span></div>
            <div className="row row--between"><span className="muted">Одобрена</span><span>{formatDate(m.approvedAt)}</span></div>
            <h3 className="mt-3">Intended use</h3>
            <p className="text-sm">{m.intendedUse || '—'}</p>
            <h3>Known limitations</h3>
            <p className="text-sm">{m.knownLimitations || '—'}</p>
          </div>
        </article>

        <article className="panel">
          <div className="panel__head"><h2>Метрики</h2></div>
          <div className="panel__body">
            <pre className="text-xs mono" style={{ background: 'var(--surface-2)', padding: 12, borderRadius: 8 }}>
{JSON.stringify(m.evaluationReport, null, 2)}
            </pre>
            <h3 className="mt-3">Calibration</h3>
            <pre className="text-xs mono" style={{ background: 'var(--surface-2)', padding: 12, borderRadius: 8 }}>
{JSON.stringify(m.calibrationProfile, null, 2)}
            </pre>
          </div>
        </article>
      </div>

      {hasRole('model_admin', 'system_admin') && transitionStates[m.state]?.length > 0 && (
        <article className="panel mt-3">
          <div className="panel__head"><h2>Действия</h2></div>
          <div className="panel__body">
            <div className="form">
              <div className="field">
                <label>Целевое состояние</label>
                <select className="select" value={targetState} onChange={(e) => setTargetState(e.target.value)}>
                  <option value="">— выберите —</option>
                  {transitionStates[m.state].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Причина (обязательно, 10+)</label>
                <textarea className="textarea" value={reason} onChange={(e) => setReason(e.target.value)} />
              </div>
              <div>
                <button className="btn btn--danger" disabled={!targetState || reason.length < 10} onClick={promote}>
                  Перевести
                </button>
              </div>
            </div>
          </div>
        </article>
      )}
    </>
  );
}
