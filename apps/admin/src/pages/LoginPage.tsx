import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth, useToasts } from '../stores/auth';
import { api, ApiError } from '../api/client';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname: string } } };
  const setSession = useAuth((s) => s.setSession);
  const accessToken = useAuth((s) => s.accessToken);
  const push = useToasts((s) => s.push);

  const [email, setEmail] = useState('admin@local');
  const [password, setPassword] = useState('change-me-now-12chars');
  const [loading, setLoading] = useState(false);

  if (accessToken) return <Navigate to={location.state?.from?.pathname ?? '/'} replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.login(email, password);
      setSession(res.access_token, res.refresh_token, res.user);
      push({ message: 'Добро пожаловать', kind: 'success' });
      navigate(location.state?.from?.pathname ?? '/');
    } catch (e) {
      const err = e as ApiError;
      push({ message: err.message || 'Не удалось войти', kind: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        background: 'var(--bg)',
      }}
    >
      <form
        className="form card"
        style={{ padding: 32, width: 360 }}
        onSubmit={handleSubmit}
        aria-label="Форма входа"
      >
        <div className="row gap-2" style={{ alignItems: 'center', marginBottom: 12 }}>
          <div className="brand__mark" style={{ width: 40, height: 40 }}>
            M
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>MimicGuard</div>
            <div className="muted text-sm">вход в админку</div>
          </div>
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <button className="btn btn--full" type="submit" disabled={loading}>
          {loading ? 'Входим…' : 'Войти'}
        </button>
        <div className="muted text-xs" style={{ marginTop: 4 }}>
          Default admin: admin@local / change-me-now-12chars
        </div>
      </form>
    </div>
  );
}
