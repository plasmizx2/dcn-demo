import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';

interface Me {
  id: string;
  email: string;
  name?: string;
  role: string;
  avatar_url?: string;
}

/**
 * For /submit, /my-jobs, /report-bug: require a signed-in user who is not a waitlister.
 * Waitlisters → /waitlist. Anonymous → /login.
 */
export function useRequireAuth() {
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
        if (u.role === 'waitlister') {
          navigate('/waitlist', { replace: true });
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
