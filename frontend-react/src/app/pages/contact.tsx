import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { Send, Mail, Eye, Clock, User, MessageSquare } from 'lucide-react';
import { apiFetch } from '../config';

interface ContactMessage {
  id: string;
  user_id: string;
  user_name?: string;
  user_email: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  created_at: string;
  status?: string;
}

interface CurrentUser {
  id: string;
  email: string;
  role: string;
}

export function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('general');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [messages, setMessages] = useState<ContactMessage[]>([]);
  const [selectedMessage, setSelectedMessage] = useState<ContactMessage | null>(null);

  useEffect(() => {
    loadCurrentUser();
  }, []);

  useEffect(() => {
    if (currentUser && (currentUser.role === 'admin' || currentUser.role === 'ceo')) {
      loadMessages();
      const interval = setInterval(loadMessages, 5000);
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

  const loadMessages = async () => {
    try {
      const response = await apiFetch('contact/messages');
      if (response.ok) {
        const data = await response.json();
        setMessages(data);
      }
    } catch (error) {
      console.debug('Contact messages endpoint not available');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await apiFetch('contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, subject, message })
      });

      if (response.ok) {
        toast.success('Message sent successfully!');
        setName('');
        setEmail('');
        setMessage('');
        if (currentUser && (currentUser.role === 'admin' || currentUser.role === 'ceo')) {
          loadMessages();
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

  const getRelativeTime = (timestamp: string) => {
    const now = new Date();
    const then = new Date(timestamp);
    const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const getSubjectBadge = (subject: string) => {
    const variants: Record<string, string> = {
      general: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
      support: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
      bug: 'bg-red-500/10 text-red-400 border-red-500/30',
      partnership: 'bg-green-500/10 text-green-400 border-green-500/30',
      other: 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    };
    return variants[subject] || variants.other;
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
              <h1 className="text-3xl lg:text-4xl font-bold text-white">Contact Us</h1>
              {isAdmin && (
                <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-400 text-xs font-semibold uppercase tracking-wider border border-purple-500/30">
                  Admin View
                </span>
              )}
            </div>
            <p className="text-slate-400 text-lg">
              Questions, feedback, or partnership inquiries — we'd love to hear from you
            </p>
          </div>

          <div className={isAdmin ? 'grid lg:grid-cols-2 gap-6' : 'max-w-3xl'}>
            {/* Contact Form */}
            <div>
              <form onSubmit={handleSubmit} className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6 lg:p-8">
                <h2 className="text-xl font-bold text-white mb-6">Send a Message</h2>
                <div className="space-y-6">
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-2">Name</label>
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Your name"
                        className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="your@email.com"
                        className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500"
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
                      <option value="general">General Inquiry</option>
                      <option value="support">Support Request</option>
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
                      placeholder="Tell us what's on your mind..."
                      rows={6}
                      className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500 resize-none"
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
            </div>

            {/* Admin: Message Log */}
            {isAdmin && (
              <div className="space-y-6">
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
                  <div className="p-4 border-b border-white/10 flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-white">All Messages</h2>
                      <p className="text-sm text-slate-400 mt-1">
                        {messages.length} total {messages.length === 1 ? 'message' : 'messages'}
                      </p>
                    </div>
                    <Mail className="w-6 h-6 text-purple-400" />
                  </div>
                  <div className="max-h-[600px] overflow-y-auto">
                    {messages.length === 0 ? (
                      <div className="p-12 text-center">
                        <MessageSquare className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                        <p className="text-slate-500">No messages yet</p>
                      </div>
                    ) : (
                      messages.map(msg => (
                        <div
                          key={msg.id}
                          onClick={() => setSelectedMessage(selectedMessage?.id === msg.id ? null : msg)}
                          className={`p-4 border-b border-white/5 cursor-pointer transition-all ${
                            selectedMessage?.id === msg.id
                              ? 'bg-purple-500/10 border-l-4 border-l-purple-500'
                              : 'hover:bg-white/5'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <User className="w-3 h-3 text-slate-500" />
                                <span className="text-sm font-semibold text-white truncate">
                                  {msg.name || msg.user_name || 'Anonymous'}
                                </span>
                              </div>
                              <p className="text-xs text-slate-400 truncate">{msg.email}</p>
                            </div>
                            <span className={`px-2 py-1 rounded-lg text-xs font-medium border ${getSubjectBadge(msg.subject)}`}>
                              {msg.subject}
                            </span>
                          </div>
                          
                          <p className="text-sm text-slate-300 line-clamp-2 mb-2">
                            {msg.message}
                          </p>
                          
                          <div className="flex items-center gap-2 text-xs text-slate-500">
                            <Clock className="w-3 h-3" />
                            {getRelativeTime(msg.created_at)}
                          </div>

                          {selectedMessage?.id === msg.id && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              className="mt-4 pt-4 border-t border-white/10"
                            >
                              <p className="text-sm text-slate-300 whitespace-pre-wrap">
                                {msg.message}
                              </p>
                            </motion.div>
                          )}
                        </div>
                      ))
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