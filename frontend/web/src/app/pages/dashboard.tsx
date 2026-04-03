import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import {
  Activity,
  Cpu,
  CheckCircle2,
  Clock,
  TrendingUp,
  Users,
  Layers,
  ShieldAlert,
  ExternalLink,
  List,
  Trash2,
} from 'lucide-react';
import { useRequireAdmin } from '../hooks/use-require-admin';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

interface MonitorStats {
  total_jobs: number;
  completed_jobs: number;
  queued_tasks: number;
  running_tasks: number;
  submitted_tasks: number;
  pending_validation_tasks: number;
  /** Workers with fresh heartbeat and status idle (waiting for tasks) */
  online_workers: number;
  /** Workers with fresh heartbeat and status busy */
  busy_workers: number;
  /** Heartbeat-OK workers: idle + busy (total connected) */
  connected_workers: number;
}

interface JobListRow {
  id: string;
  title: string;
  status: string;
  created_at?: string;
}

type QueueRow = Record<string, unknown> & {
  id?: string;
  task_name?: string;
  status?: string;
  job_title?: string;
  job_id?: string;
  job_status?: string;
};

function taskStatusClass(status: string | undefined): string {
  const s = (status || '').toLowerCase();
  if (s === 'running') return 'text-purple-400';
  if (s === 'queued') return 'text-amber-400';
  if (s === 'submitted') return 'text-emerald-400';
  if (s === 'failed') return 'text-red-400';
  if (s === 'pending_validation') return 'text-orange-400';
  return 'text-slate-400';
}

export function DashboardPage() {
  const { ready, me } = useRequireAdmin();
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobListRow[]>([]);
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    if (!ready) return;
    const loadJobs = async () => {
      try {
        const r = await fetch('/jobs', { credentials: 'include' });
        if (!r.ok) return;
        const data = await r.json();
        const sorted = [...(data as JobListRow[])].sort(
          (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime(),
        );
        setRecentJobs(sorted.slice(0, 12));
      } catch {
        /* ignore */
      }
    };
    loadJobs();
    const j = setInterval(loadJobs, 30000);
    return () => clearInterval(j);
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    const load = async () => {
      try {
        const response = await fetch('/monitor/stats', { credentials: 'include' });
        if (!response.ok) {
          setError(`Failed to load stats (${response.status})`);
          return;
        }
        const data = await response.json();
        setStats(data);
        setError(null);
      } catch {
        setError('Failed to load stats');
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    const loadQueue = async () => {
      try {
        const r = await fetch('/monitor/queue?scope=all', { credentials: 'include', cache: 'no-store' });
        if (!r.ok) {
          setQueueError(`Queue unavailable (${r.status})`);
          return;
        }
        const data = await r.json();
        setQueue(Array.isArray(data) ? data : []);
        setQueueError(null);
      } catch {
        setQueueError('Could not load queue');
      }
    };
    loadQueue();
    const q = setInterval(loadQueue, 4000);
    return () => clearInterval(q);
  }, [ready]);

  if (!ready) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[50vh]">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  const s = stats || {
    total_jobs: 0,
    completed_jobs: 0,
    queued_tasks: 0,
    running_tasks: 0,
    submitted_tasks: 0,
    pending_validation_tasks: 0,
    online_workers: 0,
    busy_workers: 0,
    connected_workers: 0,
  };

  const connected =
    typeof s.connected_workers === 'number'
      ? s.connected_workers
      : s.online_workers + s.busy_workers;

  const clearAllJobs = async () => {
    if (
      !window.confirm(
        'Delete ALL jobs, tasks, results, and events? This cannot be undone. (Admin/CEO demo reset)',
      )
    ) {
      return;
    }
    setClearing(true);
    try {
      const r = await fetch('/jobs/all', { method: 'DELETE', credentials: 'include' });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || 'Failed');
      }
      toast.success('All jobs cleared');
      const jr = await fetch('/jobs', { credentials: 'include' });
      if (jr.ok) {
        const data = await jr.json();
        const sorted = [...(data as JobListRow[])].sort(
          (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime(),
        );
        setRecentJobs(sorted.slice(0, 12));
      }
      const qr = await fetch('/monitor/queue?scope=all', { credentials: 'include' });
      if (qr.ok) {
        const qd = await qr.json();
        setQueue(Array.isArray(qd) ? qd : []);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Clear failed');
    } finally {
      setClearing(false);
    }
  };

  const statCards = [
    { label: 'Total Jobs', value: s.total_jobs, icon: Activity, iconBg: 'bg-blue-500/20', iconColor: 'text-blue-400' },
    { label: 'Completed Jobs', value: s.completed_jobs, icon: CheckCircle2, iconBg: 'bg-green-500/20', iconColor: 'text-green-400' },
    { label: 'Queued Tasks', value: s.queued_tasks, icon: TrendingUp, iconBg: 'bg-yellow-500/20', iconColor: 'text-yellow-400' },
    { label: 'Running Tasks', value: s.running_tasks, icon: Clock, iconBg: 'bg-purple-500/20', iconColor: 'text-purple-400' },
    { label: 'Finished Tasks', value: s.submitted_tasks, icon: Layers, iconBg: 'bg-indigo-500/20', iconColor: 'text-indigo-400' },
    { label: 'Pending Validation', value: s.pending_validation_tasks, icon: ShieldAlert, iconBg: 'bg-orange-500/20', iconColor: 'text-orange-400' },
    {
      label: 'Workers (idle)',
      value: s.online_workers,
      icon: Users,
      iconBg: 'bg-cyan-500/20',
      iconColor: 'text-cyan-400',
    },
    { label: 'Busy Workers', value: s.busy_workers, icon: Cpu, iconBg: 'bg-pink-500/20', iconColor: 'text-pink-400' },
  ];

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-3 text-white">Operator dashboard</h1>
              <p className="text-slate-400 text-lg">
                Live queue and workers. For <strong className="text-slate-300">per-job speedup</strong> (parallel vs
                sequential), open <Link className="text-purple-400 hover:underline" to="/jobs">All jobs</Link> → pick a
                job → <strong className="text-slate-300">Timing</strong> tab.
              </p>
            </div>
            <div className="flex items-center gap-3 flex-wrap justify-end">
              {(me?.role === 'ceo' || me?.role === 'admin') && (
                <button
                  type="button"
                  disabled={clearing}
                  onClick={clearAllJobs}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium border border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50"
                >
                  <Trash2 className="w-4 h-4" />
                  {clearing ? 'Clearing…' : 'Clear all jobs'}
                </button>
              )}
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-green-500/10 border border-green-500/30">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                <span className="text-sm text-green-400 font-medium">Live</span>
              </div>
            </div>
          </div>

          {error && (
            <p className="text-red-400 text-sm mb-4">{error}</p>
          )}

          {connected === 0 && (s.queued_tasks > 0 || s.running_tasks > 0) && (
            <p className="text-amber-400/90 text-sm mb-4 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3">
              No worker has a fresh heartbeat — queued work will not run until at least one{' '}
              <strong className="text-amber-200">dcn-worker</strong> is connected (run{' '}
              <code className="text-amber-100/90">python app.py</code> or{' '}
              <code className="text-amber-100/90">python run.py</code> on a machine that can reach this API).
            </p>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {statCards.map((stat, index) => (
              <motion.div
                key={stat.label}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: index * 0.05, duration: 0.4 }}
                className="relative group"
              >
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6 hover:border-white/20 transition-all">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`w-12 h-12 rounded-xl ${stat.iconBg} flex items-center justify-center`}>
                      <stat.icon className={`w-6 h-6 ${stat.iconColor}`} />
                    </div>
                  </div>
                  <p className="text-slate-400 text-sm mb-2 uppercase tracking-wider">{stat.label}</p>
                  <p className="text-3xl font-bold text-white">{stat.value}</p>
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="mt-8 rounded-2xl border border-amber-500/20 bg-slate-900/40 p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <List className="w-5 h-5 text-amber-400" />
              <h2 className="text-lg font-semibold text-white">Live queue</h2>
              <span className="text-xs text-slate-500">
                ({queue.length} task{queue.length === 1 ? '' : 's'} · queued, running, submitted, failed, pending
                validation · refreshes every 4s)
              </span>
            </div>
            {queueError && <p className="text-sm text-red-400 mb-2">{queueError}</p>}
            {!queueError && queue.length === 0 && (
              <p className="text-sm text-slate-500">
                Nothing queued or running right now
                {(s.queued_tasks > 0 || s.running_tasks > 0) && (
                  <span className="text-amber-400/90">
                    {' '}
                    — but stats show {s.queued_tasks + s.running_tasks} task(s) in DB; if this persists, refresh or
                    check API access.
                  </span>
                )}
                .
              </p>
            )}
            {!queueError && queue.length > 0 && (
              <div className="overflow-x-auto max-h-[280px] overflow-y-auto rounded-xl border border-white/10">
                <table className="w-full text-sm text-left">
                  <thead className="sticky top-0 bg-slate-900/95 text-xs text-slate-500 uppercase border-b border-white/10">
                    <tr>
                      <th className="p-2">Task</th>
                      <th className="p-2">Job</th>
                      <th className="p-2">Task status</th>
                      <th className="p-2">Job ID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {queue.map((row, i) => (
                      <tr key={String(row.id ?? i)} className="hover:bg-white/[0.03]">
                        <td className="p-2 text-slate-200 font-mono text-xs truncate max-w-[180px]">
                          {String(row.task_name ?? '—')}
                        </td>
                        <td className="p-2 text-slate-300 truncate max-w-[160px]">{String(row.job_title ?? '—')}</td>
                        <td className={`p-2 capitalize font-medium ${taskStatusClass(String(row.status))}`}>
                          {String(row.status ?? '—').replace(/_/g, ' ')}
                        </td>
                        <td className="p-2 text-slate-500 font-mono text-xs">
                          {row.job_id ? (
                            <Link className="text-purple-400 hover:underline" to={`/jobs#${String(row.job_id)}`}>
                              {String(row.job_id).slice(0, 8)}…
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>

          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.35, duration: 0.5 }}
            className="mt-8 rounded-2xl border border-white/10 bg-slate-900/40 p-6"
          >
            <h2 className="text-lg font-semibold text-white mb-4">Recent jobs</h2>
            {recentJobs.length === 0 ? (
              <p className="text-sm text-slate-500">No jobs yet — submit from Submit Job.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-500 uppercase border-b border-white/10">
                    <tr>
                      <th className="pb-2 pr-4">Title</th>
                      <th className="pb-2 pr-4">Status</th>
                      <th className="pb-2 pr-4">Created</th>
                      <th className="pb-2">Analysis</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {recentJobs.map((job) => (
                      <tr key={job.id} className="hover:bg-white/[0.03]">
                        <td className="py-2 pr-4 text-slate-200 max-w-[200px] truncate">{job.title}</td>
                        <td className="py-2 pr-4 capitalize text-slate-400">{job.status}</td>
                        <td className="py-2 pr-4 text-slate-500 whitespace-nowrap text-xs">
                          {job.created_at ? new Date(job.created_at).toLocaleString() : '—'}
                        </td>
                        <td className="py-2">
                          <Link
                            to={`/jobs#${job.id}`}
                            className="inline-flex items-center gap-1 text-purple-400 hover:text-purple-300 text-xs font-medium"
                          >
                            Job detail & timing
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>

          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.4, duration: 0.5 }}
            className="mt-8 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/30 rounded-2xl p-8"
          >
            <h2 className="text-2xl font-bold mb-4 text-white">Snapshot</h2>
            <div className="grid md:grid-cols-3 gap-6 text-sm">
              <div>
                <p className="text-slate-400 mb-2">Job completion rate</p>
                <p className="text-2xl font-bold text-green-400">
                  {s.total_jobs > 0 ? Math.round((s.completed_jobs / s.total_jobs) * 100) : 0}%
                </p>
              </div>
              <div>
                <p className="text-slate-400 mb-2">Workers busy / connected</p>
                <p className="text-2xl font-bold text-blue-400">
                  {s.busy_workers} / {connected}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Connected = heartbeat-OK (idle {s.online_workers} + busy {s.busy_workers})
                </p>
              </div>
              <div>
                <p className="text-slate-400 mb-2">Tasks in flight (run + queue)</p>
                <p className="text-2xl font-bold text-purple-400">{s.running_tasks + s.queued_tasks}</p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
