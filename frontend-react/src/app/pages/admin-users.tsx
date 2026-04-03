import { AdminLayout } from '../components/admin-layout';
import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { User, Shield, Clock, FileText, ChevronDown, ChevronUp, AlertCircle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

interface UserData {
  id: string;
  email: string;
  name?: string;
  role: 'customer' | 'admin' | 'ceo';
  avatar_url?: string;
  provider: string;
  created_at: string;
  last_sign_in: string;
}

interface AuditData {
  job_count: number;
  recent_jobs: Array<{
    id: string;
    title: string;
    status: string;
    created_at: string;
  }>;
  sign_in_history: Array<{
    timestamp: string;
    ip_address?: string;
  }>;
}

export function AdminUsersPage() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [auditData, setAuditData] = useState<Record<string, AuditData>>({});
  const [currentUser, setCurrentUser] = useState<UserData | null>(null);
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);

  useEffect(() => {
    // Get current user to check if CEO
    fetch('/auth/me', { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(u => setCurrentUser(u))
      .catch(() => {});

    // Load users
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const response = await fetch('/auth/users', { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      } else {
        toast.error('Failed to load users');
      }
    } catch (error) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const loadAudit = async (userId: string) => {
    if (auditData[userId]) return; // Already loaded

    try {
      const response = await fetch(`/auth/users/${userId}/audit`, { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setAuditData(prev => ({ ...prev, [userId]: data }));
      }
    } catch (error) {
      console.error('Failed to load audit data', error);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    if (currentUser?.role !== 'ceo') {
      toast.error('Only CEO can change user roles');
      return;
    }

    setUpdatingRole(userId);
    try {
      const response = await fetch('/auth/role', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ user_id: userId, role: newRole })
      });

      if (response.ok) {
        toast.success('Role updated successfully');
        loadUsers(); // Reload to get updated data
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update role');
      }
    } catch (error) {
      toast.error('Failed to update role');
    } finally {
      setUpdatingRole(null);
    }
  };

  const toggleUserDetails = (userId: string) => {
    if (selectedUser === userId) {
      setSelectedUser(null);
    } else {
      setSelectedUser(userId);
      loadAudit(userId);
    }
  };

  const isCEO = currentUser?.role === 'ceo';

  if (loading) {
    return (
      <AdminLayout>
        <div className="container mx-auto px-4 md:px-6 py-8 md:py-12">
          <div className="flex items-center justify-center py-20">
            <div className="text-slate-400">Loading users...</div>
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="container mx-auto px-4 md:px-6 py-8 md:py-12">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8">
            <h1 className="text-3xl md:text-4xl font-bold mb-3 text-white">Users & Access</h1>
            <p className="text-slate-400 text-base md:text-lg">
              Manage user roles and permissions {!isCEO && '(View only - CEO role required to edit)'}
            </p>
          </div>

          {/* User count stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {[
              { label: 'Total Users', value: users.length, color: 'purple' },
              { label: 'Admins', value: users.filter(u => u.role === 'admin' || u.role === 'ceo').length, color: 'blue' },
              { label: 'Customers', value: users.filter(u => u.role === 'customer').length, color: 'green' },
              { label: 'Active Today', value: users.filter(u => {
                const lastSignIn = new Date(u.last_sign_in);
                const today = new Date();
                return lastSignIn.toDateString() === today.toDateString();
              }).length, color: 'fuchsia' }
            ].map((stat, i) => (
              <div key={i} className="p-4 md:p-6 rounded-xl bg-slate-900/40 backdrop-blur-xl border border-white/5">
                <div className={`text-2xl md:text-3xl font-bold bg-gradient-to-r from-${stat.color}-400 to-${stat.color}-600 bg-clip-text text-transparent mb-1`}>
                  {stat.value}
                </div>
                <div className="text-xs md:text-sm text-slate-400">{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Users table */}
          <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-4 md:px-6 py-4 text-left text-xs md:text-sm font-semibold text-slate-300">User</th>
                    <th className="hidden md:table-cell px-6 py-4 text-left text-sm font-semibold text-slate-300">Provider</th>
                    <th className="px-4 md:px-6 py-4 text-left text-xs md:text-sm font-semibold text-slate-300">Role</th>
                    <th className="hidden lg:table-cell px-6 py-4 text-left text-sm font-semibold text-slate-300">Last Sign In</th>
                    <th className="px-4 md:px-6 py-4 text-right text-xs md:text-sm font-semibold text-slate-300">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <>
                      <tr key={user.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        <td className="px-4 md:px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 md:w-10 md:h-10 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-xs md:text-sm font-bold text-white flex-shrink-0">
                              {user.name?.[0] || user.email[0].toUpperCase()}
                            </div>
                            <div className="min-w-0">
                              <div className="text-xs md:text-sm font-medium text-white truncate">{user.name || user.email}</div>
                              <div className="text-[10px] md:text-xs text-slate-500 truncate">{user.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="hidden md:table-cell px-6 py-4">
                          <span className="px-2 py-1 rounded-lg bg-white/5 text-xs text-slate-400 capitalize">
                            {user.provider}
                          </span>
                        </td>
                        <td className="px-4 md:px-6 py-4">
                          {isCEO && updatingRole !== user.id ? (
                            <select
                              value={user.role}
                              onChange={(e) => handleRoleChange(user.id, e.target.value)}
                              disabled={user.id === currentUser?.id}
                              className="px-2 md:px-3 py-1 md:py-1.5 rounded-lg bg-slate-800/50 border border-white/10 text-xs md:text-sm text-white focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none disabled:opacity-50"
                            >
                              <option value="customer">Customer</option>
                              <option value="admin">Admin</option>
                              <option value="ceo">CEO</option>
                            </select>
                          ) : (
                            <span className={`inline-flex items-center gap-1 px-2 md:px-3 py-1 rounded-lg text-xs md:text-sm font-medium ${
                              user.role === 'ceo' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' :
                              user.role === 'admin' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                              'bg-slate-500/20 text-slate-400 border border-slate-500/30'
                            }`}>
                              {user.role === 'ceo' || user.role === 'admin' ? <Shield className="w-3 h-3" /> : null}
                              {user.role.toUpperCase()}
                            </span>
                          )}
                        </td>
                        <td className="hidden lg:table-cell px-6 py-4 text-sm text-slate-400">
                          {new Date(user.last_sign_in).toLocaleDateString()} {new Date(user.last_sign_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="px-4 md:px-6 py-4 text-right">
                          <button
                            onClick={() => toggleUserDetails(user.id)}
                            className="p-1.5 md:p-2 rounded-lg hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
                          >
                            {selectedUser === user.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded audit details */}
                      <AnimatePresence>
                        {selectedUser === user.id && (
                          <motion.tr
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                          >
                            <td colSpan={5} className="px-4 md:px-6 py-4 bg-slate-800/30">
                              {auditData[user.id] ? (
                                <div className="grid md:grid-cols-2 gap-4 md:gap-6">
                                  {/* Job stats */}
                                  <div>
                                    <h4 className="text-xs md:text-sm font-semibold text-white mb-3 flex items-center gap-2">
                                      <FileText className="w-4 h-4 text-purple-400" />
                                      Job Activity
                                    </h4>
                                    <div className="mb-3 p-3 rounded-lg bg-slate-900/50 border border-white/5">
                                      <div className="text-xl md:text-2xl font-bold text-purple-400">{auditData[user.id].job_count}</div>
                                      <div className="text-xs text-slate-500">Total Jobs Submitted</div>
                                    </div>
                                    {auditData[user.id].recent_jobs.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs text-slate-500 mb-2">Recent Jobs</div>
                                        {auditData[user.id].recent_jobs.slice(0, 3).map(job => (
                                          <div key={job.id} className="p-2 rounded-lg bg-slate-900/50 border border-white/5">
                                            <div className="flex items-center justify-between mb-1">
                                              <div className="text-xs md:text-sm text-white truncate flex-1">{job.title}</div>
                                              <span className={`ml-2 px-2 py-0.5 rounded text-[10px] md:text-xs font-medium ${
                                                job.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                                                job.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                                                job.status === 'running' ? 'bg-blue-500/20 text-blue-400' :
                                                'bg-yellow-500/20 text-yellow-400'
                                              }`}>
                                                {job.status}
                                              </span>
                                            </div>
                                            <div className="text-[10px] md:text-xs text-slate-500">
                                              {new Date(job.created_at).toLocaleDateString()}
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>

                                  {/* Sign in history */}
                                  <div>
                                    <h4 className="text-xs md:text-sm font-semibold text-white mb-3 flex items-center gap-2">
                                      <Clock className="w-4 h-4 text-blue-400" />
                                      Sign-In History
                                    </h4>
                                    <div className="space-y-2 max-h-64 overflow-y-auto">
                                      {auditData[user.id].sign_in_history.slice(0, 10).map((signin, idx) => (
                                        <div key={idx} className="p-2 md:p-3 rounded-lg bg-slate-900/50 border border-white/5">
                                          <div className="flex items-center gap-2 text-xs md:text-sm text-white">
                                            <CheckCircle2 className="w-3 h-3 md:w-4 md:h-4 text-green-400 flex-shrink-0" />
                                            <span className="flex-1 truncate">
                                              {new Date(signin.timestamp).toLocaleDateString()} {new Date(signin.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                          </div>
                                          {signin.ip_address && (
                                            <div className="text-[10px] md:text-xs text-slate-500 ml-5 md:ml-6 mt-1">
                                              IP: {signin.ip_address}
                                            </div>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                              ) : (
                                <div className="flex items-center justify-center py-8 text-slate-400">
                                  Loading audit data...
                                </div>
                              )}
                            </td>
                          </motion.tr>
                        )}
                      </AnimatePresence>
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            {users.length === 0 && (
              <div className="p-12 text-center">
                <AlertCircle className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400">No users found</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}