import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { Bug, Send, AlertTriangle, Clock, User, XCircle, CheckCircle2 } from 'lucide-react';
import { apiFetch } from '../config';

interface BugReport {
  id: string;
  user_id: string;
  user_name?: string;
  user_email: string;
  subject: string;
  description: string;
  page_url?: string;
  status: string;
  created_at: string;
}

interface CurrentUser {
  id: string;
  email: string;
  role: string;
}

export function ReportBugPage() {
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [pageUrl, setPageUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [bugs, setBugs] = useState<BugReport[]>([]);
  const [selectedBug, setSelectedBug] = useState<BugReport | null>(null);

  useEffect(() => {
    loadCurrentUser();
  }, []);

  useEffect(() => {
    if (currentUser && (currentUser.role === 'admin' || currentUser.role === 'ceo')) {
      loadBugs();
      const interval = setInterval(loadBugs, 5000);
      return () => clearInterval(interval);
    }
  }, [currentUser]);

  const loadCurrentUser = async () => {
    try {
      const response = await apiFetch('auth/me');
      if (response.ok) {
        const data = await response.json();
        setCurrentUser(data);
      }
    } catch (error) {
      console.debug('Auth endpoint not available');
    }
  };

  const loadBugs = async () => {
    try {
      const response = await apiFetch('bugs');
      if (response.ok) {
        const data = await response.json();
        setBugs(data);
      }
    } catch (error) {
      console.debug('Bug reports endpoint not available');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await apiFetch('bugs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
        if (currentUser && (currentUser.role === 'admin' || currentUser.role === 'ceo')) {
          loadBugs();
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

  const updateBugStatus = async (bugId: string, newStatus: string) => {
    try {
      const response = await apiFetch(`bugs/${bugId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });

      if (response.ok) {
        toast.success(`Bug marked as ${newStatus}`);
        loadBugs();
      } else {
        toast.error('Failed to update bug status');
      }
    } catch (error) {
      toast.error('Failed to update bug status');
    }
  };

  const getRelativeTime = (timestamp: string) => {
    const now = new Date();
    const then = new Date(timestamp);
    const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { bg: string; icon: any }> = {
      open: { bg: 'bg-red-500/10 text-red-400 border-red-500/30', icon: XCircle },
      investigating: { bg: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30', icon: AlertTriangle },
      resolved: { bg: 'bg-green-500/10 text-green-400 border-green-500/30', icon: CheckCircle2 }
    };
    return variants[status] || variants.open;
  };

  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'ceo';

  return (
    <AdminLayout>
      <div className="container mx-auto px-4 lg:px-6 py-8 lg:py-12">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl lg:text-4xl font-bold text-white">Report a Bug</h1>
              {isAdmin && (
                <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-400 text-xs font-semibold uppercase tracking-wider border border-purple-500/30">
                  Admin View
                </span>
              )}
            </div>
            <p className="text-slate-400 text-lg">
              Found something broken? Let us know and we'll fix it
            </p>
          </div>

          <div className={isAdmin ? 'grid lg:grid-cols-2 gap-6' : 'max-w-3xl'}>
            {/* Bug Report Form */}
            <div>
              <form onSubmit={handleSubmit} className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6 lg:p-8">
                <h2 className="text-xl font-bold text-white mb-6">Submit Bug Report</h2>
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
            </div>

            {/* Admin: Bug Report List */}
            {isAdmin && (
              <div className="space-y-6">
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
                  <div className="p-4 border-b border-white/10 flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-white">All Bug Reports</h2>
                      <p className="text-sm text-slate-400 mt-1">
                        {bugs.length} total {bugs.length === 1 ? 'report' : 'reports'} 
                        {bugs.filter(b => b.status === 'open').length > 0 && (
                          <span className="text-red-400 ml-2">
                            · {bugs.filter(b => b.status === 'open').length} open
                          </span>
                        )}
                      </p>
                    </div>
                    <Bug className="w-6 h-6 text-purple-400" />
                  </div>
                  <div className="max-h-[600px] overflow-y-auto">
                    {bugs.length === 0 ? (
                      <div className="p-12 text-center">
                        <CheckCircle2 className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                        <p className="text-slate-500">No bug reports yet</p>
                      </div>
                    ) : (
                      bugs.map(bug => {
                        const StatusIcon = getStatusBadge(bug.status).icon;
                        return (
                          <div
                            key={bug.id}
                            onClick={() => setSelectedBug(selectedBug?.id === bug.id ? null : bug)}
                            className={`p-4 border-b border-white/5 cursor-pointer transition-all ${
                              selectedBug?.id === bug.id
                                ? 'bg-purple-500/10 border-l-4 border-l-purple-500'
                                : 'hover:bg-white/5'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3 mb-2">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <User className="w-3 h-3 text-slate-500" />
                                  <span className="text-sm font-semibold text-white truncate">
                                    {bug.user_name || bug.user_email || 'Anonymous'}
                                  </span>
                                </div>
                                <p className="text-sm text-white font-semibold mb-1">{bug.subject}</p>
                                {bug.page_url && (
                                  <p className="text-xs text-slate-500 font-mono truncate">{bug.page_url}</p>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={`px-2 py-1 rounded-lg text-xs font-medium border flex items-center gap-1 ${getStatusBadge(bug.status).bg}`}>
                                  <StatusIcon className="w-3 h-3" />
                                  {bug.status}
                                </span>
                              </div>
                            </div>
                            
                            <p className="text-sm text-slate-300 line-clamp-2 mb-2">
                              {bug.description}
                            </p>
                            
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                              <Clock className="w-3 h-3" />
                              {getRelativeTime(bug.created_at)}
                            </div>

                            {selectedBug?.id === bug.id && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                className="mt-4 pt-4 border-t border-white/10 space-y-4"
                              >
                                <div>
                                  <p className="text-xs text-slate-500 mb-1">Full Description:</p>
                                  <p className="text-sm text-slate-300 whitespace-pre-wrap">
                                    {bug.description}
                                  </p>
                                </div>

                                <div className="flex gap-2">
                                  {bug.status !== 'open' && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        updateBugStatus(bug.id, 'open');
                                      }}
                                      className="px-3 py-1 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-medium transition-all border border-red-500/30"
                                    >
                                      Mark Open
                                    </button>
                                  )}
                                  {bug.status !== 'investigating' && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        updateBugStatus(bug.id, 'investigating');
                                      }}
                                      className="px-3 py-1 rounded-lg bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 text-xs font-medium transition-all border border-yellow-500/30"
                                    >
                                      Investigating
                                    </button>
                                  )}
                                  {bug.status !== 'resolved' && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        updateBugStatus(bug.id, 'resolved');
                                      }}
                                      className="px-3 py-1 rounded-lg bg-green-500/10 hover:bg-green-500/20 text-green-400 text-xs font-medium transition-all border border-green-500/30"
                                    >
                                      Mark Resolved
                                    </button>
                                  )}
                                </div>
                              </motion.div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}