import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { useRequireAdmin } from '../hooks/use-require-admin';
import { Loader2, Copy, Search } from 'lucide-react';
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

export function ResultsPage() {
  const { ready } = useRequireAdmin();
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState('rendered');
  const [loading, setLoading] = useState(true);

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
      return;
    }
    fetch(`/jobs/${selectedId}/tasks`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [selectedId]);

  useEffect(() => {
    if (typeof window === 'undefined' || !ready || !jobs.length) return;
    const hash = window.location.hash?.replace(/^#/, '');
    if (hash && jobs.some((j) => j.id === hash)) setSelectedId(hash);
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
          <h1 className="text-4xl font-bold mb-2">Results</h1>
          <p className="text-slate-400 mb-6">All jobs — select one for output and tasks</p>

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
                      setTab('rendered');
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
                    {output ? (
                      <Button variant="outline" size="sm" onClick={copyOutput}>
                        <Copy className="w-4 h-4" />
                        Copy output
                      </Button>
                    ) : null}
                  </div>

                  <Tabs value={tab} onValueChange={setTab} className="flex-1 flex flex-col p-4 min-h-0">
                    <TabsList className="bg-slate-950/80 border border-white/10 mb-3">
                      <TabsTrigger value="rendered">Rendered</TabsTrigger>
                      <TabsTrigger value="raw">Raw</TabsTrigger>
                      <TabsTrigger value="tasks">
                        Tasks ({doneTasks}/{tasks.length})
                      </TabsTrigger>
                      {looksHtml && output ? (
                        <TabsTrigger value="preview">Preview</TabsTrigger>
                      ) : null}
                    </TabsList>
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
                        {tasks.map((t) => (
                          <div
                            key={t.id}
                            className="flex items-center justify-between rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm"
                          >
                            <span className="text-slate-200">{t.task_name}</span>
                            <span className="text-xs text-slate-500 capitalize">{t.status}</span>
                          </div>
                        ))}
                        {!tasks.length && <p className="text-slate-500 text-sm">No tasks</p>}
                      </div>
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
