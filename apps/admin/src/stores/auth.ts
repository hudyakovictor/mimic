// Auth + UI state with zustand.

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CurrentUser } from '../types';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: CurrentUser | null;
  setSession: (access: string, refresh: string, user: CurrentUser) => void;
  setUser: (user: CurrentUser) => void;
  logout: () => void;
  hasRole: (...roles: string[]) => boolean;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (access, refresh, user) => {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
        set({ accessToken: access, refreshToken: refresh, user });
      },
      setUser: (user) => set({ user }),
      logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        set({ accessToken: null, refreshToken: null, user: null });
      },
      hasRole: (...roles) => {
        const u = get().user;
        if (!u) return false;
        return roles.some((r) => u.roles.includes(r)) || u.roles.includes('system_admin');
      },
    }),
    {
      name: 'mimicguard-auth',
      partialize: (s) => ({ accessToken: s.accessToken, refreshToken: s.refreshToken, user: s.user }),
    },
  ),
);

// Toast store
interface Toast {
  id: string;
  message: string;
  kind: 'info' | 'error' | 'success';
}
interface ToastState {
  toasts: Toast[];
  push: (t: Omit<Toast, 'id'>) => void;
  remove: (id: string) => void;
}
export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push: (t) => {
    const id = crypto.randomUUID();
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) }));
    }, 5000);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}));
