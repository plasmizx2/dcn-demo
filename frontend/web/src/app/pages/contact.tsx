import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Send, Inbox } from 'lucide-react';
import { useAuth } from '../hooks/use-auth';

type ContactRow = {
  id: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  created_at: string;
  user_id: string | null;
};

export function ContactPage() {
  const { user, loading: authLoading } = useAuth();
  const isElevated = user?.role === 'admin' || user?.role === 'ceo';

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('general');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [allMessages, setAllMessages] = useState<ContactRow[]>([]);
  const [listLoading, setListLoading] = useState(false);

  useEffect(() => {
    if (!isElevated || authLoading) return;
    let cancelled = false;
    setListLoading(true);
    fetch('/contact/messages', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: ContactRow[]) => {
        if (!cancelled && Array.isArray(rows)) setAllMessages(rows);
      })
      .catch(() => {
        if (!cancelled) setAllMessages([]);
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
      const response = await fetch('/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name, email, subject, message })
      });

      if (response.ok) {
        toast.success('Message sent successfully!');
        setName('');
        setEmail('');
        setMessage('');
        if (isElevated) {
          const lr = await fetch('/contact/messages', { credentials: 'include' });
          if (lr.ok) {
            const rows = await lr.json();
            if (Array.isArray(rows)) setAllMessages(rows);
          }
        }
      } else {
        toast.error('Failed to send message');
      }
    } catch (error) {
      toast.error('Failed to send message');
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
            <h1 className="text-4xl font-bold mb-3 text-white">Contact Us</h1>
            <p className="text-slate-400 text-lg">
              Questions, feedback, or partnership inquiries — we'd love to hear from you
            </p>
          </div>

          {isElevated && (
            <div className="mb-8 bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Inbox className="w-5 h-5 text-sky-400" />
                <h2 className="text-lg font-semibold text-white">All contact messages</h2>
              </div>
              {listLoading ? (
                <div className="h-24 rounded-lg bg-white/5 animate-pulse" />
              ) : allMessages.length === 0 ? (
                <p className="text-sm text-slate-500">No messages yet.</p>
              ) : (
                <div className="overflow-x-auto max-h-[420px] overflow-y-auto rounded-xl border border-white/10">
                  <table className="w-full text-sm text-left">
                    <thead className="sticky top-0 bg-slate-900/95 text-slate-400 text-xs uppercase tracking-wide">
                      <tr>
                        <th className="p-3 font-medium">When</th>
                        <th className="p-3 font-medium">From</th>
                        <th className="p-3 font-medium">Subject</th>
                        <th className="p-3 font-medium">Message</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {allMessages.map((m) => (
                        <tr key={m.id} className="hover:bg-white/[0.03]">
                          <td className="p-3 text-slate-400 whitespace-nowrap align-top">
                            {new Date(m.created_at).toLocaleString()}
                          </td>
                          <td className="p-3 text-slate-300 align-top">
                            <div>{m.name}</div>
                            <div className="text-xs text-slate-500">{m.email}</div>
                          </td>
                          <td className="p-3 text-white capitalize align-top">{m.subject}</td>
                          <td className="p-3 text-slate-400 align-top max-w-[320px] whitespace-pre-wrap break-words">
                            {m.message}
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
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Subject</label>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white"
                >
                  <option value="general">General</option>
                  <option value="support">Support</option>
                  <option value="bug">Bug Report</option>
                  <option value="partnership">Partnership</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Message</label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={6}
                  className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white resize-none"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full px-6 py-4 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:from-purple-500/50 disabled:to-blue-500/50 text-white font-semibold shadow-lg shadow-purple-500/50 transition-all flex items-center justify-center gap-2"
              >
                <Send className="w-5 h-5" />
                {loading ? 'Sending...' : 'Send Message'}
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
