import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { formatDate, formatTime } from '../lib/format';

export function PhraseDetailPage() {
  const { word = '' } = useParams<{ word: string }>();
  const [params] = useSearchParams();
  const language = params.get('lang') ?? 'en';
  const subjectId = params.get('subject') ?? undefined;

  const { data: templates = [] } = useQuery({
    queryKey: ['templates', word, language, subjectId],
    queryFn: () => api.listTemplates(decodeURIComponent(word), language, subjectId),
  });

  const latest = templates[0];
  const { data: template } = useQuery({
    queryKey: ['template', word, latest?.id],
    queryFn: () => api.getTemplate(decodeURIComponent(word), latest!.id),
    enabled: !!latest,
  });

  const { data: samples = [] } = useQuery({
    queryKey: ['samples', word, latest?.id],
    queryFn: () => api.listSamplesForWord(decodeURIComponent(word), language, latest?.id),
    enabled: !!latest,
  });

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to="/words">Слова</Link> /{' '}
            <span className="mono">{decodeURIComponent(word)}</span>
          </p>
          <h1>
            <span className="mono">{decodeURIComponent(word)}</span>{' '}
            <span className="muted text-sm">({language})</span>
          </h1>
          <p>Версий: {templates.length} · Прогонов: {samples.length}</p>
        </div>
        <div className="row gap-2">
          {latest && (
            <Link
              to={`/words/${word}/compare?lang=${language}${subjectId ? `&subject=${subjectId}` : ''}`}
              className="btn"
            >
              Сравнить версии
            </Link>
          )}
        </div>
      </header>

      <section className="grid grid--2">
        <article className="panel">
          <div className="panel__head">
            <h2>Версии шаблона</h2>
            <p>Каждое подтверждённое ревью создаёт новую версию</p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Версия</th>
                  <th>Прогонов</th>
                  <th>Mature</th>
                  <th>Модель</th>
                  <th>Создана</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((t) => (
                  <tr key={t.id}>
                    <td className="mono">v{t.version}</td>
                    <td>{t.nSamples}</td>
                    <td>
                      {t.isMature ? (
                        <span className="badge badge--consistent">зрелый</span>
                      ) : (
                        <span className="badge badge--neutral">в процессе</span>
                      )}
                    </td>
                    <td className="mono text-xs">{t.modelVersion}</td>
                    <td>
                      <small>{formatDate(t.createdAt)}</small>
                    </td>
                  </tr>
                ))}
                {templates.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted text-sm" style={{ textAlign: 'center', padding: 24 }}>
                      Шаблонов пока нет
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panel__head">
            <h2>Региональная статистика</h2>
            <p>Средние и стандартные отклонения фич</p>
          </div>
          <div className="panel__body">
            {template ? (
              <table>
                <thead>
                  <tr>
                    <th>Фича</th>
                    <th>μ</th>
                    <th>σ</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(template.regionalStats).map(([k, v]) => (
                    <tr key={k}>
                      <td className="mono text-xs">{k}</td>
                      <td className="mono">{typeof v === 'number' ? v.toFixed(4) : '—'}</td>
                      <td className="muted text-xs">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="muted text-sm">—</div>
            )}
            {template && template.meanCurve.length > 0 && (
              <div className="mt-3">
                <h3 className="text-sm">Mean curve ({template.meanCurve.length} точек × {template.meanCurve[0].length} dims)</h3>
                <div style={{ maxHeight: 200, overflow: 'auto', background: 'var(--surface-2)', borderRadius: 8, padding: 8 }}>
                  <pre className="text-xs mono" style={{ margin: 0 }}>
                    {JSON.stringify(template.meanCurve.slice(0, 5), null, 0)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </article>
      </section>

      {samples.length > 0 && (
        <article className="panel mt-3">
          <div className="panel__head">
            <h2>Verified-прогоны</h2>
            <p>{samples.length} образцов</p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Время</th>
                  <th>Кадров</th>
                  <th>DTW к шаблону</th>
                  <th>Создан</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((s) => (
                  <tr key={s.id}>
                    <td className="mono text-xs">{s.id.slice(0, 8)}</td>
                    <td className="text-sm muted">
                      {formatTime(s.startMs)} – {formatTime(s.endMs)}
                    </td>
                    <td>{s.nFrames}</td>
                    <td>{s.meanDtwToTemplate?.toFixed(3) ?? '—'}</td>
                    <td>
                      <small>{formatDate(s.createdAt)}</small>
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
