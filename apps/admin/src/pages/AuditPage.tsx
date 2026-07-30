import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { formatDate } from '../lib/format';
import { useState } from 'react';

export function AuditPage() {
  const [action, setAction] = useState('');
  const [resourceType, setResourceType] = useState('');
  const { data, isLoading, error } = useQuery({
    queryKey: ['audit', { action, resourceType }],
    queryFn: () => api.listAudit({ action: action || undefined, resourceType: resourceType || undefined, limit: 100 }),
  });

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Security</p>
          <h1>Аудит-журнал</h1>
          <p>Append-only записи всех значимых действий в системе.</p>
        </div>
        <a className="btn btn--secondary" href="/api/v1/audit/export?format=csv" download>
          Экспорт CSV
        </a>
      </header>

      <div className="filter-bar">
        <input
          className="input"
          placeholder="action (например auth.login)"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          style={{ minWidth: 220 }}
        />
        <input
          className="input"
          placeholder="resource_type"
          value={resourceType}
          onChange={(e) => setResourceType(e.target.value)}
          style={{ minWidth: 200 }}
        />
      </div>

      {isLoading ? (
        <div className="empty">Загрузка…</div>
      ) : error ? (
        <div className="empty">Ошибка</div>
      ) : !data || data.length === 0 ? (
        <div className="empty">
          <div className="empty__title">Записей нет</div>
        </div>
      ) : (
        <article className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Когда</th>
                  <th>Актор</th>
                  <th>Действие</th>
                  <th>Ресурс</th>
                  <th>IP</th>
                  <th>Причина</th>
                </tr>
              </thead>
              <tbody>
                {data.map((e: any) => (
                  <tr key={e.id}>
                    <td>
                      <small>{formatDate(e.at)}</small>
                    </td>
                    <td>
                      <span className="mono text-xs">{e.actorId ? e.actorId.slice(0, 8) : '—'}</span>
                    </td>
                    <td>
                      <span className="badge badge--neutral">{e.action}</span>
                    </td>
                    <td>
                      <span className="mono text-xs">{e.resourceType}/{e.resourceId?.slice(0, 8) ?? '—'}</span>
                    </td>
                    <td>
                      <small className="mono">{e.ip ?? '—'}</small>
                    </td>
                    <td>
                      <small>{e.reason ?? '—'}</small>
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
