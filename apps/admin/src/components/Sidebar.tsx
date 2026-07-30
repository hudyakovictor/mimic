import { NavLink } from 'react-router-dom';
import { useAuth } from '../stores/auth';

const NAV: { to: string; label: string; icon: string; roles?: string[] }[] = [
  { to: '/', label: 'Обзор', icon: '⌂' },
  { to: '/analyses', label: 'Анализы', icon: '≡' },
  { to: '/words', label: 'Слова', icon: '◊' },
  { to: '/subjects', label: 'Субъекты', icon: '⚇' },
  { to: '/reviews', label: 'Проверки', icon: '✓' },
  { to: '/models', label: 'Модели', icon: '◫' },
  { to: '/audit', label: 'Аудит', icon: '⎙', roles: ['auditor', 'system_admin'] },
  { to: '/settings', label: 'Настройки', icon: '⚙', roles: ['system_admin'] },
];

export function Sidebar() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand__mark">M</div>
        <div>
          <div className="brand__name">MimicGuard</div>
          <div className="brand__sub">Landmarks</div>
        </div>
      </div>
      <nav className="nav" aria-label="Основная навигация">
        {NAV.filter((n) => !n.roles || (user && n.roles.some((r) => user.roles.includes(r)))).map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/'}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <span className="nav__icon" aria-hidden>
              {n.icon}
            </span>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar__bottom">
        <div className="user">
          <div className="avatar">{(user?.displayName ?? user?.email ?? '?').slice(0, 2).toUpperCase()}</div>
          <div style={{ minWidth: 0 }}>
            <div className="truncate" style={{ fontWeight: 700 }}>
              {user?.displayName || user?.email}
            </div>
            <div className="truncate" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              {user?.roles[0] ?? 'guest'}
            </div>
          </div>
        </div>
        <button className="btn btn--secondary btn--sm" onClick={logout}>
          Выйти
        </button>
      </div>
    </aside>
  );
}
