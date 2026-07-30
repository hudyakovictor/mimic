import { useAuth } from '../stores/auth';

export function SettingsPage() {
  const user = useAuth((s) => s.user);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Конфигурация</p>
          <h1>Настройки тенанта</h1>
        </div>
      </header>

      <div className="grid grid--2">
        <article className="panel">
          <div className="panel__head"><h2>Тенант</h2></div>
          <div className="panel__body">
            <div className="row row--between"><span className="muted">Slug</span><span className="mono">{user?.tenantSlug}</span></div>
            <div className="row row--between"><span className="muted">ID</span><span className="mono text-xs">{user?.tenantId}</span></div>
          </div>
        </article>

        <article className="panel">
          <div className="panel__head"><h2>Текущий пользователь</h2></div>
          <div className="panel__body">
            <div className="row row--between"><span className="muted">Email</span><span>{user?.email}</span></div>
            <div className="row row--between"><span className="muted">Имя</span><span>{user?.displayName}</span></div>
            <div className="row row--between"><span className="muted">Роли</span>
              <div className="row gap-1" style={{ flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                {user?.roles.map((r) => (
                  <span key={r} className="badge badge--neutral">{r}</span>
                ))}
              </div>
            </div>
          </div>
        </article>
      </div>

      <article className="panel mt-3">
        <div className="panel__head"><h2>Retention</h2></div>
        <div className="panel__body">
          <p className="muted text-sm">
            Настройка retention policies появится в следующей итерации. Сейчас действует
            default: raw video — 90 дней, derived landmarks — 365 дней, decisions/audit — 7 лет.
          </p>
        </div>
      </article>
    </>
  );
}
