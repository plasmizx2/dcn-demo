import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';

interface Me {
  id: string;
  email: string;
  name?: string;
  role: string;
  avatar_url?: string;
}

/** Redirects if not signed in, or if role is not admin/ceo. Used for /ops, /jobs, /worker-logs, /admin/users. */
export function useRequireAdmin() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/auth/me', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((u: Me | null) => {
        if (cancelled) return;
        if (!u) {
          navigate('/login', { replace: true });
          return;
        }
        if (u.role !== 'admin' && u.role !== 'ceo') {
          navigate('/submit', { replace: true });
          return;
        }
        setMe(u);
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) navigate('/login', { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return { ready, me };
}
