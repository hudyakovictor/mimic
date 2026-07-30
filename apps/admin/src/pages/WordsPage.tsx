import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { formatRelative } from '../lib/format';

export function WordsPage() {
  const [search, setSearch] = useState('');
  const [language, setLanguage] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const { data: subjects = [] } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.listSubjects(),
  });
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['words', { language, subjectId }],
    queryFn: () =>
      api.listWords({
        language: language || undefined,
        subjectId: subjectId || undefined,
        limit: 200,
      }),
  });

  const filtered = (data ?? []).filter((w) =>
    search ? w.word.toLowerCase().includes(search.toLowerCase()) : true,
  );

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">База</p>
          <h1>Слова и словосочетания</h1>
          <p>Накопленная база произнесённых слов с verified-прогонами и шаблонами.</p>
        </div>
      </header>

      <div className="filter-bar">
        <input
          className="input"
          placeholder="Поиск по слову…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ minWidth: 240 }}
        />
        <select className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="">Все языки</option>
          <option value="en">English</option>
          <option value="ru">Русский</option>
        </select>
        <select className="select" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
          <option value="">Все субъекты</option>
          {subjects.map((subject) => (
            <option key={subject.id} value={subject.id}>
              {subject.displayName || subject.externalId}
            </option>
          ))}
        </select>
        <span className="spacer" />
        <small className="muted">Всего: {filtered.length}</small>
        <button className="btn btn--secondary btn--sm" onClick={() => refetch()}>
          Обновить
        </button>
      </div>

      {isLoading ? (
        <div className="empty">Загрузка…</div>
      ) : error ? (
        <div className="empty">Ошибка</div>
      ) : filtered.length === 0 ? (
        <div className="empty">
          <div className="empty__title">База пуста</div>
          <p>
            База наполняется, когда ревьюер подтверждает «genuine» ревью по решению с распознанной речью.
          </p>
        </div>
      ) : (
        <article className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Слово</th>
                  <th>Язык</th>
                  <th>Субъект</th>
                  <th>Версий</th>
                  <th>Прогонов</th>
                  <th>Mature</th>
                  <th>Обновлено</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((w) => {
                  const subject = subjects.find((item) => item.id === w.subjectId);
                  const query = new URLSearchParams({ lang: w.language });
                  if (w.subjectId) query.set('subject', w.subjectId);
                  return (
                    <tr key={`${w.word}-${w.language}-${w.subjectId ?? 'global'}`}>
                    <td>
                      <Link to={`/words/${encodeURIComponent(w.word)}?${query.toString()}`}>
                        <strong>{w.word}</strong>
                      </Link>
                    </td>
                    <td>
                      <span className="badge badge--neutral">{w.language}</span>
                    </td>
                    <td className="text-xs">
                      {subject?.displayName || subject?.externalId || w.subjectId?.slice(0, 8) || 'global'}
                    </td>
                    <td>{w.nTemplates}</td>
                    <td>{w.nSamples}</td>
                    <td>
                      {w.hasMatureBaseline ? (
                        <span className="badge badge--consistent">зрелый</span>
                      ) : (
                        <span className="badge badge--neutral">в процессе</span>
                      )}
                    </td>
                    <td>
                      <small>{formatRelative(w.lastUpdated)}</small>
                    </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>
      )}
    </>
  );
}
