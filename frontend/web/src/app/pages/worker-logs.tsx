import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { useRequireAdmin } from '../hooks/use-require-admin';
import { Loader2, Cpu, Trash2 } from 'lucide-react';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';

interface WorkerNode {
  id: string;
  node_name: string;
  status: string;
  last_heartbeat?: string;
  created_at?: string;
}

interface HistoryRow {
  task_name?: string;
  task_id?: string;
  job_title?: string;
  job_id?: string;
  status?: string;
  execution_time_seconds?: number;
  created_at?: string;
}

function timeAgo(iso?: string) {
  if (!iso) return 'never';
  const d = new Date(iso);
  if (isNaN(d.getTime())) {
    return 'never';
  }
  const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function WorkerLogsPage() {
  const { ready } = useRequireAdmin();
  const [workers, setWorkers] = useState<WorkerNode[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryRow[] | null>(null);
  const [loadingWorkers, setLoadingWorkers] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadWorkers = useCallback(async () => {
    try {
      const resp = await fetch('/monitor/workers', { credentials: 'include' });
      const data = await resp.json();
      if (!resp.ok) {
        setErr(typeof data.detail === 'string' ? data.detail : 'Failed to load workers');
        setWorkers([]);
        return;
      }
      setWorkers(Array.isArray(data) ? data : []);
      setErr(null);
    } catch {
      setErr('Failed to load workers');
      setWorkers([]);
    } finally {
      setLoadingWorkers(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    loadWorkers();
    const t = setInterval(loadWorkers, 5000);
    return () => clearInterval(t);
  }, [ready, loadWorkers]);

  useEffect(() => {
    if (!selectedId || !ready) {
      setHistory(null);
      return;
    }
    let cancelled = false;
    setLoadingHistory(true);
    fetch(`/monitor/worker-history/${encodeURIComponent(selectedId)}`, { credentials: 'include' })
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'History error');
        return data as HistoryRow[];
      })
      .then((rows) => {
        if (!cancelled) setHistory(Array.isArray(rows) ? rows : []);
      })
      .catch(() => {
        if (!cancelled) setHistory([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, ready]);

  const removeWorker = async (workerId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Remove this worker from the registry? Running tasks will be re-queued.')) return;
    try {
      const r = await fetch(`/monitor/workers/${encodeURIComponent(workerId)}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Failed to remove worker');
      }
      toast.success('Worker removed');
      if (selectedId === workerId) setSelectedId(null);
      await loadWorkers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove worker');
    }
  };

  const selectedWorker = workers.find((w) => w.id === selectedId);

  if (!ready || loadingWorkers) {
    return (
      <AdminLayout>
        <div className="container mx-auto px-6 py-12 max-w-6xl">
          <Skeleton className="h-10 w-56 mb-2" />
          <Skeleton className="h-5 w-80 mb-6" />
          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <Skeleton className="h-4 w-20 mb-3" />
              <div className="grid gap-3 sm:grid-cols-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="rounded-xl border border-white/10 bg-slate-900/50 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Skeleton className="w-4 h-4 rounded" />
                      <Skeleton className="h-5 w-28" />
                    </div>
                    <Skeleton className="h-3 w-24 mb-1" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 min-h-[320px]">
              <Skeleton className="h-4 w-28 mb-3" />
              <Skeleton className="h-4 w-52" />
            </div>
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-6xl">
        <motion.div initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
          <h1 className="text-4xl font-bold mb-2">Worker logs</h1>
          <p className="text-slate-400 mb-6">Registered workers and recent task history</p>
          {err && <p className="text-red-400 text-sm mb-4">{err}</p>}

          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">Workers</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {workers.map((w) => {
                  const st = (w.status || 'offline').toLowerCase();
                  return (
                    <div
                      key={w.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedId(w.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedId(w.id);
                        }
                      }}
                      className={`text-left rounded-xl border p-4 transition-colors cursor-pointer ${
                        selectedId === w.id
                          ? 'border-purple-500/50 bg-purple-500/10'
                          : 'border-white/10 bg-slate-900/50 hover:border-white/20'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <Cpu className="w-4 h-4 text-slate-500 flex-shrink-0" />
                          <span className="font-medium text-white truncate">{w.node_name}</span>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <button
                            type="button"
                            onClick={(e) => removeWorker(w.id, e)}
                            className="p-1.5 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
                            title="Remove worker"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                          <span
                            className={`text-xs uppercase font-semibold px-2 py-0.5 rounded ${
                              st === 'online'
                                ? 'bg-green-500/20 text-green-400'
                                : st === 'busy'
                                  ? 'bg-blue-500/20 text-blue-400'
                                  : 'bg-slate-500/20 text-slate-400'
                            }`}
                          >
                            {st}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-500">
                        Heartbeat: {timeAgo(w.last_heartbeat)}
                      </p>
                      <p className="text-xs text-slate-600 mt-1">
                        Since{' '}
                        {w.created_at ? new Date(w.created_at).toLocaleDateString() : '—'}
                      </p>
                    </div>
                  );
                })}
              </div>
              {!workers.length && (
                <p className="text-slate-500 text-sm py-8 text-center">No workers registered yet.</p>
              )}
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 min-h-[320px]">
              <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Task history
              </h2>
              {!selectedId && (
                <p className="text-slate-500 text-sm">Select a worker to view history.</p>
              )}
              {selectedId && loadingHistory && (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                </div>
              )}
              {selectedId && !loadingHistory && history && (
                <>
                  {selectedWorker && (
                    <p className="text-white font-medium mb-1">{selectedWorker.node_name}</p>
                  )}
                  {!history.length ? (
                    <p className="text-slate-500 text-sm py-6">No tasks processed yet.</p>
                  ) : (
                    <>
                      <p className="text-xs text-slate-500 mb-3">
                        {history.length} task(s) ·{' '}
                        {history.filter((h) => h.status === 'submitted').length} completed ·{' '}
                        {history.filter((h) => h.status === 'failed').length} failed
                      </p>
                      <div className="overflow-x-auto max-h-[480px] overflow-y-auto rounded-lg border border-white/10">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-slate-500 text-xs uppercase border-b border-white/10">
                              <th className="p-2">Task</th>
                              <th className="p-2">Job</th>
                              <th className="p-2">Status</th>
                              <th className="p-2">Time</th>
                              <th className="p-2">When</th>
                            </tr>
                          </thead>
                          <tbody>
                            {history.map((h, i) => (
                              <tr key={`${h.task_id}-${i}`} className="border-b border-white/5">
                                <td className="p-2 text-slate-300">
                                  {h.task_name || (h.task_id ? String(h.task_id).slice(0, 8) : '—')}
                                </td>
                                <td className="p-2 text-slate-400 truncate max-w-[120px]">
                                  {h.job_title || '—'}
                                </td>
                                <td className="p-2">
                                  <span className="text-xs capitalize text-slate-400">{h.status || '—'}</span>
                                </td>
                                <td className="p-2 text-slate-500 text-xs">
                                  {h.execution_time_seconds != null && isFinite(h.execution_time_seconds)
                                    ? `${Number(h.execution_time_seconds).toFixed(1)}s`
                                    : '—'}
                                </td>
                                <td className="p-2 text-slate-500 text-xs whitespace-nowrap">
                                  {h.created_at
                                    ? new Date(h.created_at).toLocaleString()
                                    : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
