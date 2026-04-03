import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Bug, Inbox } from 'lucide-react';
import { useAuth } from '../hooks/use-auth';

type BugRow = {
  id: string;
  subject: string;
  description: string;
  page_url: string | null;
  status: string | null;
  created_at: string;
  reporter_email: string | null;
  reporter_name: string | null;
};

export function ReportBugPage() {
  const { user, loading: authLoading } = useAuth();
  const isElevated = user?.role === 'admin' || user?.role === 'ceo';

  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [pageUrl, setPageUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [allBugs, setAllBugs] = useState<BugRow[]>([]);
  const [listLoading, setListLoading] = useState(false);

  useEffect(() => {
    if (!isElevated || authLoading) return;
    let cancelled = false;
    setListLoading(true);
    fetch('/bugs', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: BugRow[]) => {
        if (!cancelled && Array.isArray(rows)) setAllBugs(rows);
      })
      .catch(() => {
        if (!cancelled) setAllBugs([]);
      })
      .finally(() => {
        if (!cancelled) setListLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isElevated, authLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await fetch('/bugs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          subject,
          description,
          page_url: pageUrl || window.location.href
        })
      });

      if (response.ok) {
        toast.success('Bug report submitted! Thanks for helping us improve.');
        setSubject('');
        setDescription('');
        setPageUrl('');
        if (isElevated) {
          const lr = await fetch('/bugs', { credentials: 'include' });
          if (lr.ok) {
            const rows = await lr.json();
            if (Array.isArray(rows)) setAllBugs(rows);
          }
        }
      } else {
        toast.error('Failed to submit bug report');
      }
    } catch (error) {
      toast.error('Failed to submit bug report');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-3xl">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8">
            <h1 className="text-4xl font-bold mb-3 text-white">Report a Bug</h1>
            <p className="text-slate-400 text-lg">
              Found something broken? Let us know and we'll fix it
            </p>
          </div>

          {isElevated && (
            <div className="mb-8 bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Inbox className="w-5 h-5 text-amber-400" />
                <h2 className="text-lg font-semibold text-white">All bug reports</h2>
              </div>
              {listLoading ? (
                <div className="h-24 rounded-lg bg-white/5 animate-pulse" />
              ) : allBugs.length === 0 ? (
                <p className="text-sm text-slate-500">No reports yet.</p>
              ) : (
                <div className="overflow-x-auto max-h-[420px] overflow-y-auto rounded-xl border border-white/10">
                  <table className="w-full text-sm text-left">
                    <thead className="sticky top-0 bg-slate-900/95 text-slate-400 text-xs uppercase tracking-wide">
                      <tr>
                        <th className="p-3 font-medium">When</th>
                        <th className="p-3 font-medium">Reporter</th>
                        <th className="p-3 font-medium">Subject</th>
                        <th className="p-3 font-medium">Status</th>
                        <th className="p-3 font-medium">Page</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {allBugs.map((b) => (
                        <tr key={b.id} className="hover:bg-white/[0.03]">
                          <td className="p-3 text-slate-400 whitespace-nowrap align-top">
                            {new Date(b.created_at).toLocaleString()}
                          </td>
                          <td className="p-3 text-slate-300 align-top">
                            <div>{b.reporter_name || '—'}</div>
                            <div className="text-xs text-slate-500">{b.reporter_email || ''}</div>
                          </td>
                          <td className="p-3 text-white align-top max-w-[220px]">
                            <div className="font-medium">{b.subject}</div>
                            <p className="text-slate-400 text-xs mt-1 line-clamp-3">{b.description}</p>
                          </td>
                          <td className="p-3 text-slate-300 align-top capitalize">{b.status || 'open'}</td>
                          <td className="p-3 text-slate-400 text-xs align-top break-all max-w-[140px]">
                            {b.page_url || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Brief summary of the issue"
                  className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What happened? What did you expect to happen?"
                  rows={6}
                  className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500 resize-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Page URL / Job ID <span className="text-slate-600">(optional)</span>
                </label>
                <input
                  type="text"
                  value={pageUrl}
                  onChange={(e) => setPageUrl(e.target.value)}
                  placeholder="e.g. /my-jobs or a job ID"
                  className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500"
                />
                <p className="mt-2 text-xs text-slate-500">Auto-filled with current page if left blank</p>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full px-6 py-4 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:from-purple-500/50 disabled:to-blue-500/50 text-white font-semibold shadow-lg shadow-purple-500/50 transition-all flex items-center justify-center gap-2"
              >
                <Bug className="w-5 h-5" />
                {loading ? 'Submitting...' : 'Submit Report'}
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
