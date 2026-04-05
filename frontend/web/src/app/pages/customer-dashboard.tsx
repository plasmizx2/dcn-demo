import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import {
  Loader2,
  CheckCircle2,
  Clock,
  XCircle,
  Briefcase,
  TrendingUp,
  DollarSign,
  Plus,
  ArrowRight,
  Zap,
  CreditCard,
  Crown,
} from 'lucide-react';
import { useRequireAuth } from '../hooks/use-require-auth';

interface DashboardStats {
  total_jobs: number;
  completed_jobs: number;
  running_jobs: number;
  queued_jobs: number;
  failed_jobs: number;
  total_spend_cents: number;
  tier: string;
  recent_jobs: RecentJob[];
}

interface RecentJob {
  id: string;
  title: string;
  task_type: string;
  status: string;
  created_at: string;
  final_output?: string;
}

const money = (cents: number) =>
  new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(cents / 100);

const tierLabel: Record<string, { label: string; icon: typeof Zap; color: string }> = {
  free: { label: 'Free', icon: Zap, color: 'slate' },
  paygo: { label: 'Pay-as-you-go', icon: CreditCard, color: 'blue' },
  pro: { label: 'Pro', icon: Crown, color: 'purple' },
};

export function CustomerDashboardPage() {
  const { ready } = useRequireAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready) return;
    fetch('/dashboard/stats', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setStats(data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [ready]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/10 text-green-400 border-green-500/30';
      case 'running':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
      case 'failed':
        return 'bg-red-500/10 text-red-400 border-red-500/30';
      default:
        return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30';
    }
  };

  if (!ready || loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[50vh]">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  const tier = tierLabel[stats?.tier || 'free'] || tierLabel.free;
  const TierIcon = tier.icon;

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-8">
            <div>
              <h1 className="text-4xl font-bold mb-3 text-white">Dashboard</h1>
              <p className="text-slate-400 text-lg">Your account at a glance</p>
            </div>
            <div className="flex items-center gap-3">
              <Link
                to="/submit"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 font-semibold text-sm hover:shadow-lg hover:shadow-purple-500/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                Submit Job
              </Link>
              <Link
                to="/my-jobs"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-white/10 text-slate-300 hover:border-white/20 hover:text-white font-medium text-sm transition-all"
              >
                View All Jobs
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {[
              {
                label: 'Total Jobs',
                value: stats?.total_jobs ?? 0,
                icon: Briefcase,
                gradient: 'from-purple-500/20 to-blue-500/20',
                iconColor: 'text-purple-400',
              },
              {
                label: 'Completed',
                value: stats?.completed_jobs ?? 0,
                icon: CheckCircle2,
                gradient: 'from-green-500/20 to-emerald-500/20',
                iconColor: 'text-green-400',
              },
              {
                label: 'In Progress',
                value: (stats?.running_jobs ?? 0) + (stats?.queued_jobs ?? 0),
                icon: TrendingUp,
                gradient: 'from-blue-500/20 to-cyan-500/20',
                iconColor: 'text-blue-400',
              },
              {
                label: 'Total Spend',
                value: money(stats?.total_spend_cents ?? 0),
                icon: DollarSign,
                gradient: 'from-amber-500/20 to-orange-500/20',
                iconColor: 'text-amber-400',
              },
            ].map((card, i) => (
              <motion.div
                key={card.label}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6"
              >
                <div className="flex items-center justify-between mb-4">
                  <span className="text-sm text-slate-400">{card.label}</span>
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${card.gradient} flex items-center justify-center`}>
                    <card.icon className={`w-5 h-5 ${card.iconColor}`} />
                  </div>
                </div>
                <p className="text-3xl font-bold text-white">{card.value}</p>
              </motion.div>
            ))}
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            {/* Recent jobs */}
            <div className="lg:col-span-2">
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-white">Recent Jobs</h2>
                  <Link
                    to="/my-jobs"
                    className="text-sm text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1"
                  >
                    View all <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>

                {stats?.recent_jobs.length === 0 ? (
                  <div className="text-center py-12">
                    <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center mx-auto mb-4">
                      <Clock className="w-8 h-8 text-slate-600" />
                    </div>
                    <p className="text-slate-400 mb-4">No jobs yet</p>
                    <Link
                      to="/submit"
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 font-semibold text-sm hover:shadow-lg transition-all"
                    >
                      Submit your first job
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {stats?.recent_jobs.map((job) => (
                      <Link
                        key={job.id}
                        to="/my-jobs"
                        className="flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/5 hover:border-white/10 transition-all group"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          {getStatusIcon(job.status)}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate group-hover:text-purple-300 transition-colors">
                              {job.title}
                            </p>
                            <p className="text-xs text-slate-500">
                              {job.task_type.replace(/_/g, ' ')} &middot;{' '}
                              {new Date(job.created_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(job.status)}`}>
                          {job.status}
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Account tier */}
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                <h3 className="text-sm text-slate-400 mb-4">Account Tier</h3>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
                    <TierIcon className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <p className="font-semibold text-white">{tier.label}</p>
                    <p className="text-xs text-slate-500">
                      {stats?.tier === 'free' && '3 jobs/day'}
                      {stats?.tier === 'paygo' && 'Per-job pricing'}
                      {stats?.tier === 'pro' && 'Unlimited jobs'}
                    </p>
                  </div>
                </div>
                <Link
                  to="/account"
                  className="block text-center w-full px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-300 hover:border-white/20 hover:text-white transition-all"
                >
                  Manage Account
                </Link>
              </div>

              {/* Job breakdown */}
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                <h3 className="text-sm text-slate-400 mb-4">Job Breakdown</h3>
                <div className="space-y-3">
                  {[
                    { label: 'Completed', count: stats?.completed_jobs ?? 0, color: 'bg-green-400' },
                    { label: 'Running', count: stats?.running_jobs ?? 0, color: 'bg-blue-400' },
                    { label: 'Queued', count: stats?.queued_jobs ?? 0, color: 'bg-yellow-400' },
                    { label: 'Failed', count: stats?.failed_jobs ?? 0, color: 'bg-red-400' },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${item.color}`} />
                        <span className="text-sm text-slate-300">{item.label}</span>
                      </div>
                      <span className="text-sm font-medium text-white">{item.count}</span>
                    </div>
                  ))}
                </div>
                {(stats?.total_jobs ?? 0) > 0 && (
                  <div className="mt-4 h-2 rounded-full bg-slate-800 overflow-hidden flex">
                    {[
                      { count: stats?.completed_jobs ?? 0, color: 'bg-green-400' },
                      { count: stats?.running_jobs ?? 0, color: 'bg-blue-400' },
                      { count: stats?.queued_jobs ?? 0, color: 'bg-yellow-400' },
                      { count: stats?.failed_jobs ?? 0, color: 'bg-red-400' },
                    ]
                      .filter((s) => s.count > 0)
                      .map((s, i) => (
                        <div
                          key={i}
                          className={`${s.color} h-full`}
                          style={{ width: `${(s.count / (stats?.total_jobs || 1)) * 100}%` }}
                        />
                      ))}
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
