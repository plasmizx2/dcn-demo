import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { useRequireAdmin } from '../hooks/use-require-admin';
import { Loader2, Copy, Search, Gauge, Zap, Trash2, ScrollText } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

interface JobRow {
  id: string;
  title: string;
  task_type: string;
  status: string;
  created_at?: string;
  final_output?: string;
}

interface TaskRow {
  id: string;
  task_name: string;
  status: string;
}

interface JobTiming {
  sequential_time_seconds: number;
  parallel_time_seconds: number;
  speedup: number;
  time_saved: number;
  worker_count: number;
  total_tasks: number;
  tasks: { task_name: string; status: string; execution_time: number | null }[];
  actual_cost?: { actual_total?: number; compute_cost?: number } | null;
}

export function ResultsPage() {
  const { ready } = useRequireAdmin();
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState('rendered');
  const [loading, setLoading] = useState(true);
  const [timing, setTiming] = useState<JobTiming | null>(null);
  const [timingLoading, setTimingLoading] = useState(false);
  const [events, setEvents] = useState<JobEventRow[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadJobs = useCallback(async () => {
    try {
      const resp = await fetch('/jobs', { credentials: 'include' });
      if (!resp.ok) return;
      const data = await resp.json();
      const sorted = [...data].sort(
        (a: JobRow, b: JobRow) =>
          new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime(),
      );
      setJobs(sorted);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    loadJobs();
    const t = setInterval(loadJobs, 10000);
    return () => clearInterval(t);
  }, [ready, loadJobs]);

  const selected = jobs.find((j) => j.id === selectedId);

  useEffect(() => {
    if (!selectedId) {
      setTasks([]);
      setTiming(null);
      return;
    }
    fetch(`/jobs/${selectedId}/tasks`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then(setTasks)
      .catch(() => setTasks([]));

    setTiming(null);
    setTimingLoading(true);
    fetch(`/jobs/${selectedId}/timing`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: JobTiming | null) => {
        if (data) setTiming(data);
        else setTiming(null);
      })
      .catch(() => setTiming(null))
      .finally(() => setTimingLoading(false));

    setEvents([]);
    setEventsLoading(true);
    fetch(`/jobs/${selectedId}/events`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: JobEventRow[]) => setEvents(Array.isArray(rows) ? rows : []))
      .catch(() => setEvents([]))
      .finally(() => setEventsLoading(false));
  }, [selectedId]);

  const deleteSelectedJob = async () => {
    if (!selectedId) return;
    if (
      !window.confirm(
        'Delete this job and all its tasks, events, and results? This cannot be undone.',
      )
    ) {
      return;
    }
    setDeleting(true);
    try {
      const r = await fetch(`/jobs/${selectedId}`, { method: 'DELETE', credentials: 'include' });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || 'Delete failed');
      }
      toast.success('Job deleted');
      setSelectedId(null);
      window.location.hash = '';
      await loadJobs();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    if (typeof window === 'undefined' || !ready || !jobs.length) return;
    const hash = window.location.hash?.replace(/^#/, '');
    if (hash && jobs.some((j) => j.id === hash)) {
      setSelectedId(hash);
      const job = jobs.find((j) => j.id === hash);
      if (job?.status === 'completed') setTab('timing');
    }
  }, [ready, jobs]);

  const filtered = jobs.filter((j) => {
    if (filter !== 'all' && j.status !== filter) return false;
    const q = search.toLowerCase();
    if (q && !j.title?.toLowerCase().includes(q) && !j.task_type?.toLowerCase().includes(q)) return false;
    return true;
  });

  const copyOutput = () => {
    if (!selected?.final_output) return;
    navigator.clipboard.writeText(selected.final_output).then(() => toast.success('Copied'));
  };

  const output = selected?.final_output || '';
  const doneTasks = tasks.filter((t) => t.status === 'submitted').length;
  const looksHtml =
    output.trim().startsWith('<') || output.includes('<!DOCTYPE') || output.includes('<html');

  if (!ready || loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[50vh]">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-[1400px]">
        <motion.div initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
          <h1 className="text-4xl font-bold mb-2 text-white">Results</h1>
          <p className="text-slate-400 mb-6">
            Select a job — open the <strong className="text-slate-300">Timing</strong> tab for parallel vs
            sequential speedup (same analysis as before).
          </p>

          <div className="flex flex-col lg:flex-row gap-6 min-h-[60vh]">
            <div className="lg:w-96 flex-shrink-0 flex flex-col rounded-2xl border border-white/10 bg-slate-900/40 overflow-hidden">
              <div className="p-3 border-b border-white/10 space-y-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search title or type…"
                    className="w-full rounded-lg bg-black/30 border border-white/10 pl-9 pr-3 py-2 text-sm text-white placeholder:text-slate-500"
                  />
                </div>
                <div className="flex flex-wrap gap-1">
                  {(['all', 'completed', 'running', 'queued', 'failed'] as const).map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => setFilter(f)}
                      className={`rounded-md px-2 py-1 text-xs font-medium capitalize ${
                        filter === f
                          ? 'bg-purple-500/30 text-white'
                          : 'bg-white/5 text-slate-400 hover:bg-white/10'
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500">{filtered.length} job(s)</p>
              </div>
              <div className="flex-1 overflow-y-auto max-h-[calc(100vh-280px)]">
                {filtered.map((j) => (
                  <button
                    key={j.id}
                    type="button"
                    onClick={() => {
                      setSelectedId(j.id);
                      setTab(j.status === 'completed' ? 'timing' : 'rendered');
                      window.location.hash = j.id;
                    }}
                    className={`w-full text-left px-4 py-3 border-b border-white/5 hover:bg-white/5 ${
                      selectedId === j.id ? 'bg-purple-500/15 border-l-2 border-l-purple-500' : ''
                    }`}
                  >
                    <div className="font-medium text-white text-sm truncate">{j.title}</div>
                    <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                      <span className="capitalize">{j.status}</span>
                      <span className="text-slate-600">·</span>
                      <span>{j.task_type?.replace(/_/g, ' ')}</span>
                    </div>
                  </button>
                ))}
                {!filtered.length && (
                  <p className="p-6 text-slate-500 text-sm text-center">No jobs match</p>
                )}
              </div>
            </div>

            <div className="flex-1 rounded-2xl border border-white/10 bg-slate-900/40 flex flex-col min-h-[400px]">
              {!selected && (
                <div className="flex-1 flex items-center justify-center text-slate-500 p-8">
                  Select a job to view output
                </div>
              )}
              {selected && (
                <>
                  <div className="p-4 border-b border-white/10 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-xl font-bold text-white">{selected.title}</h2>
                      <p className="text-sm text-slate-500 mt-1">
                        <span className="capitalize">{selected.status}</span> ·{' '}
                        {selected.task_type?.replace(/_/g, ' ')} ·{' '}
                        {selected.created_at
                          ? new Date(selected.created_at).toLocaleString()
                          : ''}
                        {output ? ` · ${output.length.toLocaleString()} chars` : ''}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {output ? (
                        <Button variant="outline" size="sm" onClick={copyOutput}>
                          <Copy className="w-4 h-4" />
                          Copy output
                        </Button>
                      ) : null}
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={deleting}
                        onClick={deleteSelectedJob}
                        className="border-red-500/40 text-red-300 hover:bg-red-500/10"
                      >
                        <Trash2 className="w-4 h-4" />
                        {deleting ? 'Deleting…' : 'Delete job'}
                      </Button>
                    </div>
                  </div>

                  <Tabs value={tab} onValueChange={setTab} className="flex-1 flex flex-col p-4 min-h-0">
                    <TabsList className="bg-slate-950/80 border border-white/10 mb-3 flex-wrap">
                      <TabsTrigger value="rendered">Rendered</TabsTrigger>
                      <TabsTrigger value="raw">Raw</TabsTrigger>
                      <TabsTrigger value="timing" className="gap-1">
                        <Gauge className="w-3.5 h-3.5" />
                        Timing
                      </TabsTrigger>
                      <TabsTrigger value="tasks">
                        Tasks ({doneTasks}/{tasks.length})
                      </TabsTrigger>
                      <TabsTrigger value="events" className="gap-1">
                        <ScrollText className="w-3.5 h-3.5" />
                        Events ({events.length})
                      </TabsTrigger>
                      {looksHtml && output ? (
                        <TabsTrigger value="preview">Preview</TabsTrigger>
                      ) : null}
                    </TabsList>
                    <TabsContent value="timing" className="flex-1 overflow-auto mt-0 space-y-6">
                      {timingLoading ? (
                        <div className="flex justify-center py-12">
                          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
                        </div>
                      ) : !timing ? (
                        <p className="text-slate-500 text-sm">Could not load timing for this job.</p>
                      ) : !timing.tasks?.length ? (
                        <p className="text-slate-500 text-sm">No tasks on this job yet.</p>
                      ) : timing.sequential_time_seconds <= 0 &&
                        timing.parallel_time_seconds <= 0 &&
                        !timing.tasks.some((x) => x.execution_time != null) ? (
                        <p className="text-slate-500 text-sm">
                          Speed comparison appears after workers finish tasks and report execution times. Check back when
                          the job is further along or completed.
                        </p>
                      ) : (
                        <>
                          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Sequential (sum)</p>
                              <p className="text-2xl font-bold text-amber-300 tabular-nums">
                                {timing.sequential_time_seconds.toFixed(1)}s
                              </p>
                              <p className="text-xs text-slate-500 mt-1">One machine, tasks back-to-back</p>
                            </div>
                            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Parallel (wall)</p>
                              <p className="text-2xl font-bold text-cyan-300 tabular-nums">
                                {timing.parallel_time_seconds.toFixed(1)}s
                              </p>
                              <p className="text-xs text-slate-500 mt-1">Merged worker intervals</p>
                            </div>
                            <div className="rounded-xl border border-purple-500/30 bg-purple-500/10 p-4">
                              <p className="text-xs text-purple-300 uppercase tracking-wide mb-1 flex items-center gap-1">
                                <Zap className="w-3.5 h-3.5" /> Speedup
                              </p>
                              <p className="text-2xl font-bold text-white tabular-nums">{timing.speedup}×</p>
                              <p className="text-xs text-slate-400 mt-1">
                                {timing.time_saved.toFixed(1)}s saved vs sequential
                              </p>
                            </div>
                            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                              <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Workers used</p>
                              <p className="text-2xl font-bold text-white tabular-nums">{timing.worker_count}</p>
                              <p className="text-xs text-slate-500 mt-1">{timing.total_tasks} tasks</p>
                            </div>
                          </div>

                          <div>
                            <p className="text-sm text-slate-400 mb-2">Compare</p>
                            <div className="space-y-2">
                              <div>
                                <div className="flex justify-between text-xs text-slate-500 mb-1">
                                  <span>Sequential time</span>
                                  <span>{timing.sequential_time_seconds.toFixed(1)}s</span>
                                </div>
                                <div className="h-3 rounded-full bg-white/10 overflow-hidden">
                                  <div
                                    className="h-full bg-amber-500/80 rounded-full transition-all"
                                    style={{
                                      width: `${Math.min(
                                        100,
                                        (timing.sequential_time_seconds /
                                          Math.max(timing.sequential_time_seconds, timing.parallel_time_seconds, 0.001)) *
                                          100,
                                      )}%`,
                                    }}
                                  />
                                </div>
                              </div>
                              <div>
                                <div className="flex justify-between text-xs text-slate-500 mb-1">
                                  <span>Parallel wall time</span>
                                  <span>{timing.parallel_time_seconds.toFixed(1)}s</span>
                                </div>
                                <div className="h-3 rounded-full bg-white/10 overflow-hidden">
                                  <div
                                    className="h-full bg-cyan-500/80 rounded-full transition-all"
                                    style={{
                                      width: `${Math.min(
                                        100,
                                        (timing.parallel_time_seconds /
                                          Math.max(timing.sequential_time_seconds, timing.parallel_time_seconds, 0.001)) *
                                          100,
                                      )}%`,
                                    }}
                                  />
                                </div>
                              </div>
                            </div>
                          </div>

                          {timing.actual_cost && (
                            <p className="text-sm text-slate-400">
                              Actual compute (estimate):{' '}
                              <span className="text-emerald-400 font-mono">
                                ${Number(timing.actual_cost.actual_total ?? 0).toFixed(4)}
                              </span>
                            </p>
                          )}

                          <div>
                            <p className="text-sm font-medium text-white mb-2">Per-task execution</p>
                            <div className="rounded-xl border border-white/10 overflow-hidden max-h-[40vh] overflow-y-auto">
                              <table className="w-full text-sm">
                                <thead className="sticky top-0 bg-slate-900/95 text-left text-xs text-slate-500 uppercase">
                                  <tr>
                                    <th className="p-3">Task</th>
                                    <th className="p-3">Status</th>
                                    <th className="p-3 text-right">Seconds</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                  {(timing.tasks || []).map((row, i) => (
                                    <tr key={`${row.task_name}-${i}`} className="hover:bg-white/[0.03]">
                                      <td className="p-3 text-slate-200 font-mono text-xs">{row.task_name}</td>
                                      <td className="p-3 text-slate-500 capitalize">{row.status}</td>
                                      <td className="p-3 text-right text-cyan-300 tabular-nums">
                                        {row.execution_time != null ? row.execution_time.toFixed(2) : '—'}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </>
                      )}
                    </TabsContent>
                    <TabsContent value="rendered" className="flex-1 overflow-auto mt-0">
                      {output ? (
                        <div className="prose prose-invert prose-sm max-w-none rounded-lg border border-white/10 bg-black/20 p-4">
                          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200">{output}</pre>
                        </div>
                      ) : (
                        <p className="text-slate-500">No output yet — job is {selected.status}</p>
                      )}
                    </TabsContent>
                    <TabsContent value="raw" className="flex-1 overflow-auto mt-0">
                      <pre className="whitespace-pre-wrap text-xs text-slate-400 bg-black/30 rounded-lg p-4 border border-white/10 max-h-[55vh] overflow-auto">
                        {output || '—'}
                      </pre>
                    </TabsContent>
                    <TabsContent value="tasks" className="flex-1 overflow-auto mt-0">
                      <div className="space-y-2 max-h-[55vh] overflow-auto">
                        {tasks.map((t) => {
                          const sec = timing?.tasks?.find((x) => x.task_name === t.task_name)?.execution_time;
                          return (
                            <div
                              key={t.id}
                              className="flex items-center justify-between rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm gap-3"
                            >
                              <span className="text-slate-200 truncate">{t.task_name}</span>
                              <div className="flex items-center gap-3 shrink-0">
                                {sec != null && (
                                  <span className="text-xs text-cyan-400/90 tabular-nums">{sec.toFixed(2)}s</span>
                                )}
                                <span className="text-xs text-slate-500 capitalize">{t.status}</span>
                              </div>
                            </div>
                          );
                        })}
                        {!tasks.length && <p className="text-slate-500 text-sm">No tasks</p>}
                      </div>
                    </TabsContent>
                    <TabsContent value="events" className="flex-1 overflow-auto mt-0">
                      {eventsLoading ? (
                        <div className="flex justify-center py-12">
                          <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                        </div>
                      ) : !events.length ? (
                        <p className="text-slate-500 text-sm">No events logged for this job yet.</p>
                      ) : (
                        <div className="rounded-xl border border-white/10 overflow-hidden max-h-[55vh] overflow-y-auto">
                          <table className="w-full text-sm">
                            <thead className="sticky top-0 bg-slate-900/95 text-left text-xs text-slate-500 uppercase">
                              <tr>
                                <th className="p-3">When</th>
                                <th className="p-3">Type</th>
                                <th className="p-3">Message</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                              {events.map((ev, i) => (
                                <tr key={String(ev.id ?? i)} className="hover:bg-white/[0.03]">
                                  <td className="p-3 text-slate-500 whitespace-nowrap text-xs align-top">
                                    {ev.created_at ? new Date(ev.created_at).toLocaleString() : '—'}
                                  </td>
                                  <td className="p-3 text-amber-400/90 font-mono text-xs align-top">
                                    {ev.event_type ?? '—'}
                                  </td>
                                  <td className="p-3 text-slate-300 align-top">{ev.message ?? '—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </TabsContent>
                    {looksHtml && output ? (
                      <TabsContent value="preview" className="flex-1 mt-0 min-h-0">
                        <div className="rounded-lg border border-white/10 overflow-hidden bg-white h-[55vh]">
                          <iframe
                            title="preview"
                            className="w-full h-full"
                            sandbox="allow-scripts"
                            srcDoc={output.replace(/^=== .+ ===\s*/gm, '').replace(/```html?\s*/gi, '').replace(/```\s*/g, '')}
                          />
                        </div>
                      </TabsContent>
                    ) : null}
                  </Tabs>
                </>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
