import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { RiskRing } from '../components/RiskRing';
import { useToasts } from '../stores/auth';
import { formatDate, formatPercent, formatTime } from '../lib/format';

export function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>();
  const push = useToasts((s) => s.push);
  const qc = useQueryClient();
  const [showReview, setShowReview] = useState(false);

  const { data: job, isLoading, error, refetch } = useQuery({
    queryKey: ['job', id],
    queryFn: () => api.getJob(id!),
    enabled: !!id,
    refetchInterval: (q) => {
      const s = (q.state.data as any)?.state;
      return s === 'QUEUED' || s === 'RUNNING' ? 3000 : false;
    },
  });

  // Side-by-side compare: load decision phrases + baseline samples
  void job; // sample URLs are loaded on demand from the compare page

  if (isLoading) {
    return (
      <div className="empty">
        <div className="empty__title">Загрузка…</div>
      </div>
    );
  }
  if (error || !job) {
    return (
      <div className="empty">
        <div className="empty__title">Не удалось загрузить</div>
        <button className="btn mt-2" onClick={() => refetch()}>
          Повторить
        </button>
      </div>
    );
  }

  const dec = job.decision;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to="/analyses">Анализы</Link> / {job.id.slice(0, 8)}
          </p>
          <h1>Анализ {job.id.slice(0, 8)}</h1>
          <p className="muted text-sm">
            Создан {formatDate(job.createdAt)}
            {job.attempt > 1 && ` · попытка ${job.attempt}`}
          </p>
        </div>
        <div className="row gap-2">
          {job.state === 'SUCCEEDED' && dec && (
            <Link to={`/analyses/${job.id}/compare`} className="btn btn--secondary">
              Side-by-side
            </Link>
          )}
          {(job.state === 'QUEUED' || job.state === 'RUNNING') && (
            <button
              className="btn btn--secondary"
              onClick={async () => {
                try {
                  await api.cancelJob(job.id);
                  push({ message: 'Анализ отменён', kind: 'info' });
                  qc.invalidateQueries({ queryKey: ['job', id] });
                } catch (e: any) {
                  push({ message: e.message, kind: 'error' });
                }
              }}
            >
              Отменить
            </button>
          )}
          {(job.state === 'FAILED' || job.state === 'INSUFFICIENT_DATA') && (
            <button
              className="btn"
              onClick={async () => {
                try {
                  await api.retryJob(job.id);
                  push({ message: 'Анализ перезапущен', kind: 'success' });
                  qc.invalidateQueries({ queryKey: ['job', id] });
                } catch (e: any) {
                  push({ message: e.message, kind: 'error' });
                }
              }}
            >
              Повторить
            </button>
          )}
        </div>
      </header>

      <section className="grid grid--main">
        <article className="panel">
          <div className="panel__head">
            <div>
              <h2>Решение</h2>
              <p>Итог работы пайплайна по этому анализу</p>
            </div>
            {dec && <StatusBadge value={dec.label} />}
          </div>
          <div className="panel__body">
            {dec ? (
              <div>
                <RiskRing value={dec.riskScore} />
                <div className="row row--between mt-2">
                  <span className="muted text-sm">Качество</span>
                  <span>{formatPercent(dec.qualityScore)}</span>
                </div>
                <div className="row row--between">
                  <span className="muted text-sm">Модель</span>
                  <span className="mono text-xs">{dec.modelVersion}</span>
                </div>
                <div className="row row--between">
                  <span className="muted text-sm">Checksum</span>
                  <span className="mono text-xs">{dec.modelChecksum.slice(0, 16) || '—'}</span>
                </div>
                {dec.evidence.length > 0 && (
                  <div className="mt-3">
                    <h3 className="text-sm">Evidence ({dec.evidence.length})</h3>
                    <div className="evidence">
                      {dec.evidence.map((e, i) => (
                        <div key={i} className="evidence__item">
                          <span>{e.contribution > 0 ? '+' : ''}{Math.round(e.contribution * 100)}</span>
                          <div>
                            <strong>{e.message}</strong>
                            <small>
                              {e.code}
                              {e.word && ` · ${e.word}`}
                              {e.startMs != null && e.endMs != null && ` · ${formatTime(e.startMs)}–${formatTime(e.endMs)}`}
                            </small>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <button className="btn btn--full mt-3" onClick={() => setShowReview((s) => !s)}>
                  Записать ревью
                </button>
                {showReview && (
                  <ReviewForm
                    decisionId={dec.id}
                    onClose={() => setShowReview(false)}
                    onCreated={() => {
                      setShowReview(false);
                      qc.invalidateQueries({ queryKey: ['reviews'] });
                      push({ message: 'Ревью записано', kind: 'success' });
                    }}
                  />
                )}
              </div>
            ) : (
              <div className="empty">
                <div className="empty__title">Решение ещё не готово</div>
                <p>Состояние пайплайна: {job.state}</p>
                {job.lastError && <p className="error">{job.lastError}</p>}
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel__head">
            <div>
              <h2>Этапы пайплайна</h2>
              <p>{job.stages.length} шагов выполнено</p>
            </div>
          </div>
          <div className="panel__body">
            <ol style={{ paddingLeft: 0, listStyle: 'none', margin: 0 }}>
              {job.stages.map((s) => (
                <li key={s.id} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  <div className="row row--between">
                    <span style={{ fontWeight: 600 }}>{s.name}</span>
                    <StatusBadge value={s.state} />
                  </div>
                  {s.error && <small className="error">{s.error}</small>}
                  {s.startedAt && (
                    <small className="muted">
                      {formatDate(s.startedAt)}
                      {s.completedAt && ` — ${formatDate(s.completedAt)}`}
                    </small>
                  )}
                </li>
              ))}
              {job.stages.length === 0 && (
                <li className="muted text-sm">Этапы ещё не начались</li>
              )}
            </ol>
          </div>
        </article>
      </section>

      {dec && dec.phraseInstances.length > 0 && (
        <article className="panel mt-3">
          <div className="panel__head">
            <div>
              <h2>Распознанные слова</h2>
              <p>Сравнение с персональным baseline по каждому слову</p>
            </div>
            <Link
              to={`/words/${encodeURIComponent(dec.phraseInstances[0].word)}/compare?lang=${dec.phraseInstances[0].language}&subject=${job.subjectId}`}
              className="btn btn--secondary btn--sm"
            >
              Сравнить
            </Link>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Слово</th>
                  <th>Время</th>
                  <th>Сходство</th>
                  <th>Baseline</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {dec.phraseInstances.map((pi, i) => (
                  <tr key={i}>
                    <td>
                      <Link to={`/words/${encodeURIComponent(pi.word)}?lang=${pi.language}&subject=${job.subjectId}`}>{pi.word}</Link>
                    </td>
                    <td className="text-sm muted">
                      {formatTime(pi.startMs)} – {formatTime(pi.endMs)}
                    </td>
                    <td>{formatPercent(pi.similarity)}</td>
                    <td>
                      {pi.hasMatureBaseline ? (
                        <span className="badge badge--consistent">зрелый</span>
                      ) : (
                        <span className="badge badge--neutral">в процессе</span>
                      )}
                    </td>
                    <td>
                      {pi.evidence.length > 0 ? (
                        <span className="text-xs">{pi.evidence.map((e) => e.code).join(', ')}</span>
                      ) : (
                        <span className="muted text-xs">—</span>
                      )}
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

function ReviewForm({
  decisionId,
  onClose,
  onCreated,
}: {
  decisionId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [verdict, setVerdict] = useState('CONFIRMED_GENUINE');
  const [reason, setReason] = useState('');
  const [confidence, setConfidence] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (reason.length < 10) {
      setErr('Минимум 10 символов');
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      await api.createReview({ decisionId, verdict, reason, confidence });
      onCreated();
    } catch (e: any) {
      setErr(e.message || 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="form mt-3" onSubmit={submit}>
      <div className="field">
        <label>Вердикт</label>
        <select className="select" value={verdict} onChange={(e) => setVerdict(e.target.value)}>
          <option value="CONFIRMED_GENUINE">Подтверждено подлинное</option>
          <option value="CONFIRMED_SUSPICIOUS">Подтверждено подозрение</option>
          <option value="UNDECIDABLE">Не решено</option>
        </select>
      </div>
      <div className="field">
        <label>Причина (10–2000)</label>
        <textarea
          className="textarea"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          required
        />
      </div>
      <div className="field">
        <label>Уверенность (опц.)</label>
        <input
          className="input"
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={confidence ?? ''}
          onChange={(e) => setConfidence(e.target.value ? Number(e.target.value) : undefined)}
        />
      </div>
      {err && <div className="error">{err}</div>}
      <div className="row gap-2" style={{ justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn--secondary" onClick={onClose}>
          Отмена
        </button>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? 'Сохранение…' : 'Сохранить ревью'}
        </button>
      </div>
    </form>
  );
}
