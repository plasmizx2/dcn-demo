import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { useRequireAdmin } from '../hooks/use-require-admin';
import { Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

interface DirectoryUser {
  id: string;
  email: string;
  name?: string;
  provider: string;
  role: string;
  created_at: string;
}

interface AuditData {
  job_stats: { total_jobs?: number; by_status?: Record<string, number> };
  jobs: Array<{
    id: string;
    title: string;
    task_type: string;
    status: string;
    created_at?: string;
  }>;
  sessions: {
    active_session_count?: number;
    recent_logins?: string[];
  };
}

export function AdminUsersPage() {
  const { ready, me } = useRequireAdmin();
  const [users, setUsers] = useState<DirectoryUser[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditData | null>(null);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [roleChoice, setRoleChoice] = useState<'customer' | 'admin'>('customer');
  const [savingRole, setSavingRole] = useState(false);

  const loadUsers = useCallback(async () => {
    const ur = await fetch('/auth/users', { credentials: 'include' });
    if (!ur.ok) {
      setLoadErr(await ur.text());
      return;
    }
    setUsers(await ur.json());
    setLoadErr(null);
  }, []);

  useEffect(() => {
    if (!ready) return;
    loadUsers();
  }, [ready, loadUsers]);

  const selected = users.find((u) => u.id === selectedId);

  useEffect(() => {
    if (!selectedId || !ready) {
      setAudit(null);
      return;
    }
    let cancelled = false;
    setLoadingAudit(true);
    fetch(`/auth/users/${encodeURIComponent(selectedId)}/audit`, { credentials: 'include' })
      .then(async (r) => {
        if (!r.ok) throw new Error('audit failed');
        return r.json();
      })
      .then((data: AuditData) => {
        if (!cancelled) setAudit(data);
      })
      .catch(() => {
        if (!cancelled) setAudit(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingAudit(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, ready]);

  useEffect(() => {
    if (selected) {
      setRoleChoice(selected.role === 'admin' ? 'admin' : 'customer');
    }
  }, [selected?.id, selected?.role]);

  const canEditRole =
    me?.role === 'ceo' && selected && selected.role !== 'ceo' && selected.id !== me.id;

  const saveRole = async () => {
    if (!selectedId || !canEditRole) return;
    setSavingRole(true);
    try {
      const pr = await fetch('/auth/role', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: selectedId, role: roleChoice }),
      });
      const body = await pr.json().catch(() => ({}));
      if (!pr.ok) {
        toast.error(typeof body.detail === 'string' ? body.detail : 'Could not update role');
        return;
      }
      toast.success('Role updated');
      await loadUsers();
    } finally {
      setSavingRole(false);
    }
  };

  if (!ready) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[50vh]">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  const by = audit?.job_stats?.by_status || {};
  const recent = audit?.jobs || [];
  const logins = audit?.sessions?.recent_logins || [];

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-6xl">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-4xl font-bold mb-3">Users &amp; access</h1>
          <p className="text-slate-400 text-lg mb-6 max-w-2xl">
            OAuth directory, roles, and job history. CEOs can assign <strong className="text-slate-300">admin</strong> or{' '}
            <strong className="text-slate-300">customer</strong>. The CEO account is tied to <code className="text-purple-400">CEO_EMAIL</code>.
          </p>

          {me?.role === 'ceo' && (
            <div className="mb-6 rounded-xl border border-purple-500/30 bg-purple-500/10 px-4 py-3 text-sm text-slate-300">
              <strong className="text-purple-300">CEO</strong> — Use the role control for users below (not CEO accounts).
            </div>
          )}
          {me?.role === 'admin' && (
            <div className="mb-6 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-400">
              <strong className="text-slate-300">Admin</strong> — Read-only directory. Ask a CEO to change roles.
            </div>
          )}

          {loadErr && <p className="text-red-400 text-sm mb-4">{loadErr}</p>}

          <div className="grid lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 overflow-hidden">
              <div className="px-4 py-3 border-b border-white/10 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Accounts
              </div>
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 text-xs uppercase">
                      <th className="p-3">User</th>
                      <th className="p-3">Provider</th>
                      <th className="p-3">Role</th>
                      <th className="p-3">Joined</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr
                        key={u.id}
                        onClick={() => setSelectedId(u.id)}
                        className={`cursor-pointer border-t border-white/5 hover:bg-white/5 ${
                          selectedId === u.id ? 'bg-purple-500/15' : ''
                        }`}
                      >
                        <td className="p-3">
                          <div className="font-medium text-white">{u.email}</div>
                          <div className="text-xs text-slate-500">{u.name || '—'}</div>
                        </td>
                        <td className="p-3 text-slate-400">{u.provider}</td>
                        <td className="p-3">
                          <span
                            className={`inline-block rounded-md px-2 py-0.5 text-xs font-semibold uppercase ${
                              u.role === 'ceo'
                                ? 'bg-amber-500/20 text-amber-300'
                                : u.role === 'admin'
                                  ? 'bg-blue-500/20 text-blue-300'
                                  : 'bg-white/10 text-slate-400'
                            }`}
                          >
                            {u.role}
                          </span>
                        </td>
                        <td className="p-3 text-slate-500 text-xs">
                          {u.created_at ? new Date(u.created_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!users.length && !loadErr && (
                  <p className="p-6 text-slate-500 text-center text-sm">No users yet.</p>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/50 min-h-[200px]">
              <div className="px-4 py-3 border-b border-white/10 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Selected user
              </div>
              <div className="p-5">
                {!selectedId && (
                  <p className="text-slate-500 text-sm">Select a row to see audit data and role controls.</p>
                )}
                {selectedId && loadingAudit && (
                  <div className="flex justify-center py-12">
                    <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                  </div>
                )}
                {selectedId && !loadingAudit && selected && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-lg font-semibold text-white">{selected.email}</h3>
                      {canEditRole && (
                        <div className="mt-3 flex flex-wrap items-center gap-3">
                          <label className="text-sm text-slate-400">Role</label>
                          <select
                            value={roleChoice}
                            onChange={(e) => setRoleChoice(e.target.value as 'customer' | 'admin')}
                            className="rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm text-white"
                          >
                            <option value="customer">customer</option>
                            <option value="admin">admin</option>
                          </select>
                          <Button size="sm" onClick={saveRole} disabled={savingRole}>
                            {savingRole ? 'Saving…' : 'Save role'}
                          </Button>
                        </div>
                      )}
                      {!canEditRole && (
                        <p className="mt-2 text-sm text-slate-500">
                          Role: <strong className="text-slate-300">{selected.role}</strong>
                          {selected.role === 'ceo' && ' (via CEO_EMAIL)'}
                        </p>
                      )}
                    </div>

                    {audit && (
                      <>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="rounded-lg bg-black/20 p-3">
                            <span className="text-xs text-slate-500 uppercase">Total jobs</span>
                            <p className="text-xl font-bold">{audit.job_stats?.total_jobs ?? 0}</p>
                          </div>
                          <div className="rounded-lg bg-black/20 p-3">
                            <span className="text-xs text-slate-500 uppercase">Active sessions</span>
                            <p className="text-xl font-bold">{audit.sessions?.active_session_count ?? 0}</p>
                          </div>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 uppercase mb-1">Jobs by status</p>
                          <p className="text-sm text-slate-400">
                            {Object.keys(by).length
                              ? Object.entries(by)
                                  .map(([k, v]) => `${k}: ${v}`)
                                  .join(' · ')
                              : 'None yet'}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 uppercase mb-2">Recent jobs</p>
                          <div className="max-h-40 overflow-auto rounded-lg border border-white/10">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-slate-500 text-left">
                                  <th className="p-2">Title</th>
                                  <th className="p-2">Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {recent.length === 0 && (
                                  <tr>
                                    <td colSpan={2} className="p-3 text-slate-500">
                                      No jobs
                                    </td>
                                  </tr>
                                )}
                                {recent.map((j) => (
                                  <tr key={j.id} className="border-t border-white/5">
                                    <td className="p-2 text-slate-300">{j.title}</td>
                                    <td className="p-2 text-slate-400">{j.status}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 uppercase mb-1">Recent sign-ins</p>
                          <div className="font-mono text-xs text-slate-400 max-h-32 overflow-auto">
                            {logins.length ? logins.join('\n') : 'No session rows'}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
