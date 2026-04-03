import { useEffect, useState } from 'react';

export interface AuthUser {
  email: string;
  name: string;
  avatar_url: string | null;
  role: string;
}

/** Loads current user from cookie-backed GET /auth/me (same-origin). */
export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch('/auth/me', { credentials: 'include' })
      .then((r) => {
        if (!r.ok) {
          if (!cancelled) setUser(null);
          return null;
        }
        return r.json();
      })
      .then((data: AuthUser | null) => {
        if (!cancelled && data) setUser(data);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, loading, isAuthenticated: !!user };
}
