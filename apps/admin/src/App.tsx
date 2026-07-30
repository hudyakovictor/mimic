import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { useAuth, useToasts } from './stores/auth';
import { api, ApiError, isAuthError } from './api/client';
import { DashboardPage } from './pages/DashboardPage';
import { AnalysesPage } from './pages/AnalysesPage';
import { AnalysisDetailPage } from './pages/AnalysisDetailPage';
import { AnalysisComparePage } from './pages/AnalysisComparePage';
import { WordsPage } from './pages/WordsPage';
import { PhraseDetailPage } from './pages/PhraseDetailPage';
import { PhraseComparePage } from './pages/PhraseComparePage';
import { SubjectsPage } from './pages/SubjectsPage';
import { SubjectDetailPage } from './pages/SubjectDetailPage';
import { ReviewsPage } from './pages/ReviewsPage';
import { ReviewDetailPage } from './pages/ReviewDetailPage';
import { ModelsPage } from './pages/ModelsPage';
import { ModelDetailPage } from './pages/ModelDetailPage';
import { AuditPage } from './pages/AuditPage';
import { SettingsPage } from './pages/SettingsPage';
import { LoginPage } from './pages/LoginPage';
import { Sidebar } from './components/Sidebar';
import { Toasts } from './components/Toasts';

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const accessToken = useAuth((s) => s.accessToken);
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const logout = useAuth((s) => s.logout);
  const location = useLocation();
  const push = useToasts((s) => s.push);

  useEffect(() => {
    if (accessToken && !user) {
      api
        .me()
        .then((u) => setUser(u))
        .catch((e) => {
          if (isAuthError(e)) {
            logout();
            push({ message: 'Сессия истекла', kind: 'error' });
          }
        });
    }
  }, [accessToken, user, setUser, logout, push]);

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return (
    <div className="shell">
      <Sidebar />
      <main>{children}</main>
      <Toasts />
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <DashboardPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/analyses"
        element={
          <ProtectedLayout>
            <AnalysesPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/analyses/:id"
        element={
          <ProtectedLayout>
            <AnalysisDetailPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/analyses/:id/compare"
        element={
          <ProtectedLayout>
            <AnalysisComparePage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/words"
        element={
          <ProtectedLayout>
            <WordsPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/words/:word"
        element={
          <ProtectedLayout>
            <PhraseDetailPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/words/:word/compare"
        element={
          <ProtectedLayout>
            <PhraseComparePage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/subjects"
        element={
          <ProtectedLayout>
            <SubjectsPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/subjects/:id"
        element={
          <ProtectedLayout>
            <SubjectDetailPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/reviews"
        element={
          <ProtectedLayout>
            <ReviewsPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/reviews/:id"
        element={
          <ProtectedLayout>
            <ReviewDetailPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/models"
        element={
          <ProtectedLayout>
            <ModelsPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/models/:id"
        element={
          <ProtectedLayout>
            <ModelDetailPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/audit"
        element={
          <ProtectedLayout>
            <AuditPage />
          </ProtectedLayout>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedLayout>
            <SettingsPage />
          </ProtectedLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// Handle global 401 by clearing session
export function withErrorBoundary<P extends object>(Component: React.ComponentType<P>) {
  return function Wrapped(props: P) {
    const logout = useAuth((s) => s.logout);
    const push = useToasts((s) => s.push);
    useEffect(() => {
      const onUnhandled = (e: PromiseRejectionEvent) => {
        if (e.reason instanceof ApiError) {
          if (e.reason.status === 401) {
            logout();
            push({ message: 'Требуется повторный вход', kind: 'error' });
          } else if (e.reason.status >= 500) {
            push({ message: 'Ошибка сервера', kind: 'error' });
          }
        }
      };
      window.addEventListener('unhandledrejection', onUnhandled);
      return () => window.removeEventListener('unhandledrejection', onUnhandled);
    }, [logout, push]);
    return <Component {...(props as P & React.JSX.IntrinsicAttributes)} />;
  };
}
