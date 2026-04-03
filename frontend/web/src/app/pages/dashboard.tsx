import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { Activity, Cpu, CheckCircle2, Clock, TrendingUp, Users } from 'lucide-react';

interface Stats {
  total_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  queued_jobs: number;
  total_tasks: number;
  worker_count: number;
  active_workers: number;
}

export function DashboardPage() {
  const [stats, setStats] = useState<Stats>({
    total_jobs: 0,
    running_jobs: 0,
    completed_jobs: 0,
    queued_jobs: 0,
    total_tasks: 0,
    worker_count: 0,
    active_workers: 0,
  });

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadStats = async () => {
    try {
      const response = await fetch('/stats', { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to load stats');
    }
  };

  const statCards = [
    {
      label: 'Total Jobs',
      value: stats.total_jobs,
      icon: Activity,
      color: 'from-blue-500 to-cyan-500',
      iconBg: 'bg-blue-500/20',
      iconColor: 'text-blue-400'
    },
    {
      label: 'Running',
      value: stats.running_jobs,
      icon: Clock,
      color: 'from-purple-500 to-pink-500',
      iconBg: 'bg-purple-500/20',
      iconColor: 'text-purple-400'
    },
    {
      label: 'Completed',
      value: stats.completed_jobs,
      icon: CheckCircle2,
      color: 'from-green-500 to-emerald-500',
      iconBg: 'bg-green-500/20',
      iconColor: 'text-green-400'
    },
    {
      label: 'Queued',
      value: stats.queued_jobs,
      icon: TrendingUp,
      color: 'from-yellow-500 to-orange-500',
      iconBg: 'bg-yellow-500/20',
      iconColor: 'text-yellow-400'
    },
    {
      label: 'Total Tasks',
      value: stats.total_tasks,
      icon: Cpu,
      color: 'from-indigo-500 to-purple-500',
      iconBg: 'bg-indigo-500/20',
      iconColor: 'text-indigo-400'
    },
    {
      label: 'Active Workers',
      value: `${stats.active_workers}/${stats.worker_count}`,
      icon: Users,
      color: 'from-pink-500 to-rose-500',
      iconBg: 'bg-pink-500/20',
      iconColor: 'text-pink-400'
    },
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
              <h1 className="text-4xl font-bold mb-3">Dashboard</h1>
              <p className="text-slate-400 text-lg">Real-time system overview</p>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-green-500/10 border border-green-500/30">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              <span className="text-sm text-green-400 font-medium">Live</span>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {statCards.map((stat, index) => (
              <motion.div
                key={index}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
                className="relative group"
              >
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6 hover:border-white/20 transition-all">
                  <div className="flex items-start justify-between mb-4">
                    <div className={`w-12 h-12 rounded-xl ${stat.iconBg} flex items-center justify-center`}>
                      <stat.icon className={`w-6 h-6 ${stat.iconColor}`} />
                    </div>
                    <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm mb-2 uppercase tracking-wider">{stat.label}</p>
                    <p className="text-3xl font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent">
                      {stat.value}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Additional Info */}
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.7, duration: 0.5 }}
            className="mt-8 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/30 rounded-2xl p-8"
          >
            <h2 className="text-2xl font-bold mb-4">System Status</h2>
            <div className="grid md:grid-cols-3 gap-6">
              <div>
                <p className="text-slate-400 text-sm mb-2">Job Completion Rate</p>
                <p className="text-2xl font-bold text-green-400">
                  {stats.total_jobs > 0 
                    ? Math.round((stats.completed_jobs / stats.total_jobs) * 100)
                    : 0}%
                </p>
              </div>
              <div>
                <p className="text-slate-400 text-sm mb-2">Worker Utilization</p>
                <p className="text-2xl font-bold text-blue-400">
                  {stats.worker_count > 0
                    ? Math.round((stats.active_workers / stats.worker_count) * 100)
                    : 0}%
                </p>
              </div>
              <div>
                <p className="text-slate-400 text-sm mb-2">Tasks/Job Average</p>
                <p className="text-2xl font-bold text-purple-400">
                  {stats.total_jobs > 0
                    ? Math.round(stats.total_tasks / stats.total_jobs)
                    : 0}
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
