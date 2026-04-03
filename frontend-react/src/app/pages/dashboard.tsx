import { AdminLayout } from '../components/admin-layout';
import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { 
  CheckCircle2, Clock, TrendingUp, Users, Zap, AlertCircle, 
  Trash2, XCircle, Loader2, Activity, BarChart3, FileText,
  AlertTriangle, UserX, ChevronRight, Download
} from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../config';

interface MonitorStats {
  total_jobs: number;
  completed_jobs: number;
  queued_tasks: number;
  running_tasks: number;
  submitted_tasks: number;
  online_workers: number;
  busy_workers: number;
}

interface Job {
  id: string;
  title: string;
  task_type: string;
  status: string;
  created_at: string;
  has_output: boolean;
}

interface Worker {
  id: string;
  name: string;
  status: string;
  last_heartbeat: string;
  current_task?: {
    id: string;
    name: string;
  };
}

interface QueueTask {
  id: string;
  job_id: string;
  task_name: string;
  tier: number;
  status: string;
  worker_id?: string;
}

interface JobDetail {
  id: string;
  title: string;
  task_type: string;
  status: string;
  created_at: string;
  final_output?: string;
}

interface Task {
  id: string;
  order: number;
  task_name: string;
  tier: number;
  status: string;
  worker_id?: string;
  failure_detail?: string;
}

interface JobTiming {
  parallel_time: number;
  sequential_time: number;
  speedup: number;
  worker_count: number;
  time_saved: number;
}

interface JobEvent {
  id: string;
  event_type: string;
  message: string;
  created_at: string;
}

interface User {
  id: string;
  email: string;
  name?: string;
  role: string;
}

export function DashboardPage() {
  const [stats, setStats] = useState<MonitorStats>({
    total_jobs: 0,
    completed_jobs: 0,
    queued_tasks: 0,
    running_tasks: 0,
    submitted_tasks: 0,
    online_workers: 0,
    busy_workers: 0
  });
  const [jobs, setJobs] = useState<Job[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [queue, setQueue] = useState<QueueTask[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [timing, setTiming] = useState<JobTiming | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    loadCurrentUser();
    pollAll();
    const interval = setInterval(pollAll, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      loadJobDetail(selectedJobId);
      loadJobEvents(selectedJobId);
    }
  }, [selectedJobId]);

  const loadCurrentUser = async () => {
    try {
      const response = await apiFetch('auth/me');
      if (response.ok) {
        const data = await response.json();
        setCurrentUser(data);
      }
    } catch (error) {
      console.error('Failed to load current user');
    }
  };

  const pollAll = async () => {
    await Promise.all([
      loadStats(),
      loadJobs(),
      loadWorkers(),
      loadQueue(),
      loadUsers()
    ]);
  };

  const loadStats = async () => {
    try {
      const response = await apiFetch('monitor/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      // Silently fail if endpoint doesn't exist
      console.debug('Stats endpoint not available');
    }
  };

  const loadJobs = async () => {
    try {
      const response = await apiFetch('monitor/jobs');
      if (response.ok) {
        const data = await response.json();
        setJobs(data);
        
        // Auto-select first running/queued job, else newest
        if (!selectedJobId && data.length > 0) {
          const runningOrQueued = data.find((j: Job) => j.status === 'running' || j.status === 'queued');
          setSelectedJobId(runningOrQueued?.id || data[0].id);
        }
      }
    } catch (error) {
      // Silently fail if endpoint doesn't exist
      console.debug('Jobs endpoint not available');
    }
  };

  const loadWorkers = async () => {
    try {
      const response = await apiFetch('monitor/workers');
      if (response.ok) {
        const data = await response.json();
        setWorkers(data);
      }
    } catch (error) {
      // Silently fail if endpoint doesn't exist
      console.debug('Workers endpoint not available');
    }
  };

  const loadQueue = async () => {
    try {
      const response = await apiFetch('monitor/queue');
      if (response.ok) {
        const data = await response.json();
        setQueue(data);
      }
    } catch (error) {
      // Silently fail if endpoint doesn't exist
      console.debug('Queue endpoint not available');
    }
  };

  const loadJobDetail = async (jobId: string) => {
    try {
      const [jobRes, tasksRes, timingRes] = await Promise.all([
        apiFetch(`jobs/${jobId}`),
        apiFetch(`jobs/${jobId}/tasks`),
        apiFetch(`jobs/${jobId}/timing`).catch(() => null)
      ]);

      if (jobRes.ok) {
        const jobData = await jobRes.json();
        setJobDetail(jobData);
      }

      if (tasksRes.ok) {
        const tasksData = await tasksRes.json();
        setTasks(tasksData);
      }

      if (timingRes && timingRes.ok) {
        const timingData = await timingRes.json();
        setTiming(timingData);
      } else {
        setTiming(null);
      }
    } catch (error) {
      // Silently fail if endpoint doesn't exist
      console.debug('Job detail endpoint not available');
    }
  };

  const loadJobEvents = async (jobId: string) => {
    try {
      const response = await apiFetch(`jobs/${jobId}/events`);
      if (response.ok) {
        const data = await response.json();
        setEvents(data);
      }
    } catch (error) {
      // Silently fail if endpoint doesn't exist
      console.debug('Events endpoint not available');
    }
  };

  const loadUsers = async () => {
    if (currentUser?.role !== 'ceo') return;
    
    try {
      const response = await apiFetch('auth/users');
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (error) {
      // Silently fail if endpoint doesn't exist
      console.debug('Users endpoint not available');
    }
  };

  const clearAllJobs = async () => {
    if (!confirm('Are you sure you want to delete ALL jobs? This cannot be undone.')) {
      return;
    }

    try {
      const response = await apiFetch('jobs/all', { method: 'DELETE' });
      if (response.ok) {
        toast.success('All jobs cleared');
        setSelectedJobId(null);
        setJobDetail(null);
        setTasks([]);
        setEvents([]);
        await pollAll();
      } else {
        toast.error('Failed to clear jobs');
      }
    } catch (error) {
      toast.error('Failed to clear jobs');
    }
  };

  const revokeWorker = async (workerId: string) => {
    if (!confirm('Revoke this worker? Running tasks will be requeued.')) {
      return;
    }

    try {
      const response = await apiFetch(`monitor/workers/${workerId}`, { method: 'DELETE' });
      if (response.ok) {
        toast.success('Worker revoked');
        await pollAll();
      } else {
        toast.error('Failed to revoke worker');
      }
    } catch (error) {
      toast.error('Failed to revoke worker');
    }
  };

  const changeUserRole = async (userId: string, newRole: string) => {
    try {
      const response = await apiFetch('auth/role', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, role: newRole })
      });

      if (response.ok) {
        toast.success(`User role changed to ${newRole}`);
        await loadUsers();
      } else {
        toast.error('Failed to change role');
      }
    } catch (error) {
      toast.error('Failed to change role');
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
    const variants: Record<string, string> = {
      completed: 'bg-green-500/10 text-green-400 border-green-500/30',
      running: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
      queued: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
      failed: 'bg-red-500/10 text-red-400 border-red-500/30',
      'pending validation': 'bg-purple-500/10 text-purple-400 border-purple-500/30'
    };
    return variants[status] || 'bg-slate-500/10 text-slate-400 border-slate-500/30';
  };

  const getTierBadge = (tier: number) => {
    const colors = ['bg-blue-500/20 text-blue-300', 'bg-green-500/20 text-green-300', 'bg-yellow-500/20 text-yellow-300', 'bg-red-500/20 text-red-300'];
    return colors[tier - 1] || colors[0];
  };

  const completedTasks = tasks.filter(t => t.status === 'completed').length;
  const runningTasksCount = tasks.filter(t => t.status === 'running').length;
  const progress = tasks.length > 0 ? (completedTasks / tasks.length) * 100 : 0;

  return (
    <AdminLayout>
      <div className="container mx-auto px-4 lg:px-6 py-8 lg:py-12">
        {/* Header */}
        <div className="mb-8 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl lg:text-4xl font-bold text-white">Dashboard</h1>
              <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-400 text-xs font-semibold uppercase tracking-wider border border-purple-500/30">
                OPS
              </span>
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/10 border border-green-500/30">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                <span className="text-xs text-green-400 font-medium">Live</span>
              </div>
            </div>
            <p className="text-slate-400">Real-time system monitoring</p>
          </div>
          <button
            onClick={clearAllJobs}
            className="px-4 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 font-medium transition-all flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Clear All Jobs
          </button>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 lg:gap-4 mb-8">
          {[
            { label: 'Total Jobs', value: stats.total_jobs, icon: FileText },
            { label: 'Completed', value: stats.completed_jobs, icon: CheckCircle2 },
            { label: 'Queued Tasks', value: stats.queued_tasks, icon: Clock },
            { label: 'Running Tasks', value: stats.running_tasks, icon: Activity },
            { label: 'Submitted', value: stats.submitted_tasks, icon: TrendingUp },
            { label: 'Online Workers', value: stats.online_workers, icon: Users },
            { label: 'Busy Workers', value: stats.busy_workers, icon: Zap }
          ].map((stat, i) => (
            <motion.div
              key={i}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: i * 0.05 }}
              className="bg-slate-900/50 backdrop-blur-xl rounded-xl border border-white/10 p-3 lg:p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className="w-4 h-4 text-purple-400" />
                <p className="text-xs text-slate-400 uppercase tracking-wider truncate">{stat.label}</p>
              </div>
              <p className="text-2xl font-bold text-white">{stat.value}</p>
            </motion.div>
          ))}
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Jobs Table */}
            <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <h2 className="text-xl font-bold text-white">Jobs</h2>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {jobs.length === 0 ? (
                  <div className="p-8 text-center text-slate-500">No jobs</div>
                ) : (
                  jobs.map(job => (
                    <div
                      key={job.id}
                      onClick={() => setSelectedJobId(job.id)}
                      className={`p-4 border-b border-white/5 cursor-pointer transition-all ${
                        selectedJobId === job.id
                          ? 'bg-purple-500/10 border-l-4 border-l-purple-500'
                          : 'hover:bg-white/5'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-mono text-slate-500">#{job.id.substring(0, 8)}</span>
                            <span className="text-sm font-semibold text-white truncate">{job.title}</span>
                          </div>
                          <div className="flex items-center gap-2 text-xs">
                            <span className="px-2 py-0.5 rounded bg-slate-700/50 text-slate-300">
                              {job.task_type.replace(/_/g, ' ')}
                            </span>
                            <span className="text-slate-500">{getRelativeTime(job.created_at)}</span>
                            <span className={job.has_output ? 'text-green-400' : 'text-slate-600'}>
                              {job.has_output ? '✓' : '—'}
                            </span>
                          </div>
                        </div>
                        <span className={`px-2 py-1 rounded-lg text-xs font-medium border ${getStatusBadge(job.status)}`}>
                          {job.status}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Worker Activity */}
            <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <h2 className="text-xl font-bold text-white">Worker Activity</h2>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {workers.length === 0 ? (
                  <div className="p-8 text-center text-slate-500">No workers online</div>
                ) : (
                  workers.map(worker => (
                    <div key={worker.id} className="p-4 border-b border-white/5 hover:bg-white/5 transition-all">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className={`w-2 h-2 rounded-full ${worker.status === 'online' ? 'bg-green-400' : 'bg-slate-600'}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-white truncate">{worker.name}</p>
                            <p className="text-xs text-slate-400">
                              {worker.current_task ? worker.current_task.name : 'idle'} · {getRelativeTime(worker.last_heartbeat)}
                            </p>
                          </div>
                        </div>
                        {currentUser?.role === 'admin' && (
                          <button
                            onClick={() => revokeWorker(worker.id)}
                            className="px-2 py-1 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs transition-all"
                          >
                            <UserX className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Active Queue */}
            <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <h2 className="text-xl font-bold text-white">Active Queue</h2>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {queue.length === 0 ? (
                  <div className="p-8 text-center text-slate-500">Queue empty</div>
                ) : (
                  queue.map(task => (
                    <div key={task.id} className="p-3 border-b border-white/5 hover:bg-white/5 transition-all">
                      <div className="flex items-center gap-3 text-xs">
                        <span className="font-mono text-slate-500">#{task.id.substring(0, 6)}</span>
                        <span className="font-mono text-slate-600">job:{task.job_id.substring(0, 6)}</span>
                        <span className="text-slate-300 truncate flex-1">{task.task_name}</span>
                        <span className={`px-2 py-0.5 rounded font-semibold ${getTierBadge(task.tier)}`}>
                          T{task.tier}
                        </span>
                        <span className={`px-2 py-0.5 rounded border ${getStatusBadge(task.status)}`}>
                          {task.status}
                        </span>
                        {task.worker_id && (
                          <span className="text-slate-500">w:{task.worker_id.substring(0, 6)}</span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Job Detail */}
          <div className="space-y-6">
            {selectedJobId && jobDetail ? (
              <>
                {/* Job Header */}
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h2 className="text-2xl font-bold text-white mb-2">{jobDetail.title}</h2>
                      <div className="flex items-center gap-3 text-sm">
                        <span className="px-3 py-1 rounded-lg bg-purple-500/10 text-purple-400 font-medium">
                          {jobDetail.task_type.replace(/_/g, ' ')}
                        </span>
                        <span className="text-slate-500">#{jobDetail.id.substring(0, 8)}</span>
                      </div>
                    </div>
                    <span className={`px-3 py-1 rounded-lg text-sm font-medium border ${getStatusBadge(jobDetail.status)}`}>
                      {jobDetail.status}
                    </span>
                  </div>

                  {/* Progress */}
                  {tasks.length > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-2 text-sm">
                        <span className="text-slate-400">
                          {completedTasks}/{tasks.length} tasks · {Math.round(progress)}%
                        </span>
                        {runningTasksCount > 0 && (
                          <span className="text-blue-400">{runningTasksCount} running</span>
                        )}
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${progress}%` }}
                          className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Tasks Table */}
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
                  <div className="p-4 border-b border-white/10">
                    <h3 className="font-bold text-white">Tasks ({tasks.length})</h3>
                  </div>
                  <div className="max-h-96 overflow-y-auto">
                    {tasks.map(task => (
                      <div key={task.id} className="p-3 border-b border-white/5">
                        <div className="flex items-start gap-3">
                          <span className="text-xs font-mono text-slate-500 mt-1">#{task.order}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-white mb-1 truncate">{task.task_name}</p>
                            {task.failure_detail && (
                              <p className="text-xs text-red-400 bg-red-500/10 rounded px-2 py-1 mt-1">
                                {task.failure_detail.substring(0, 100)}...
                              </p>
                            )}
                          </div>
                          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getTierBadge(task.tier)}`}>
                            T{task.tier}
                          </span>
                          <span className={`px-2 py-0.5 rounded text-xs border ${getStatusBadge(task.status)}`}>
                            {task.status}
                          </span>
                          {task.worker_id && (
                            <span className="text-xs font-mono text-slate-500">w:{task.worker_id.substring(0, 6)}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Timing Chart */}
                {timing && jobDetail.status === 'completed' && (
                  <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                    <h3 className="font-bold text-white mb-4">Performance</h3>
                    <div className="space-y-4">
                      <div>
                        <div className="flex items-center justify-between mb-2 text-sm">
                          <span className="text-slate-400">Parallel Time</span>
                          <span className="text-white font-semibold">{timing.parallel_time.toFixed(1)}s</span>
                        </div>
                        <div className="h-8 bg-slate-800 rounded-lg overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-green-500 to-emerald-500" style={{ width: '100%' }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center justify-between mb-2 text-sm">
                          <span className="text-slate-400">Sequential Time (est.)</span>
                          <span className="text-white font-semibold">{timing.sequential_time.toFixed(1)}s</span>
                        </div>
                        <div className="h-8 bg-slate-800 rounded-lg overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-red-500 to-orange-500"
                            style={{ width: `${(timing.sequential_time / timing.sequential_time) * 100}%` }}
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-4 pt-4 border-t border-white/10">
                        <div>
                          <p className="text-xs text-slate-400 mb-1">Speedup</p>
                          <p className="text-lg font-bold text-green-400">{timing.speedup.toFixed(2)}x</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-400 mb-1">Workers</p>
                          <p className="text-lg font-bold text-blue-400">{timing.worker_count}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-400 mb-1">Time Saved</p>
                          <p className="text-lg font-bold text-purple-400">{timing.time_saved.toFixed(1)}s</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Final Output */}
                {jobDetail.final_output && (
                  <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
                    <div className="p-4 border-b border-white/10 flex items-center justify-between">
                      <h3 className="font-bold text-white">Final Output</h3>
                      <button className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">
                        <Download className="w-3 h-3" />
                        Download
                      </button>
                    </div>
                    <div className="p-4 max-h-96 overflow-y-auto">
                      <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
                        {jobDetail.final_output.substring(0, 2000)}
                        {jobDetail.final_output.length > 2000 && '...'}
                      </pre>
                    </div>
                  </div>
                )}

                {/* Event Feed */}
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
                  <div className="p-4 border-b border-white/10">
                    <h3 className="font-bold text-white">Event Feed</h3>
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {events.length === 0 ? (
                      <div className="p-8 text-center text-slate-500 text-sm">No events</div>
                    ) : (
                      events.map(event => (
                        <div key={event.id} className="p-3 border-b border-white/5">
                          <div className="flex items-start gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold">
                                  {event.event_type}
                                </span>
                                <span className="text-xs text-slate-500">{getRelativeTime(event.created_at)}</span>
                              </div>
                              <p className="text-sm text-slate-300">{event.message}</p>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-12 text-center">
                <BarChart3 className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                <h3 className="text-xl font-bold text-white mb-2">No Job Selected</h3>
                <p className="text-slate-400">Select a job from the list to view details</p>
              </div>
            )}
          </div>
        </div>

        {/* CEO User Management */}
        {currentUser?.role === 'ceo' && users.length > 0 && (
          <div className="mt-8 bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-2xl p-6">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <Users className="w-5 h-5" />
              User Management (CEO)
            </h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {users.map(user => (
                <div key={user.id} className="bg-slate-900/50 rounded-xl p-4 border border-white/10">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-white truncate">{user.name || user.email}</p>
                      <p className="text-xs text-slate-500 truncate">{user.email}</p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-xs bg-purple-500/20 text-purple-300 capitalize">
                      {user.role}
                    </span>
                  </div>
                  {user.id !== currentUser.id && (
                    <div className="mt-3 flex gap-2">
                      {user.role !== 'admin' && (
                        <button
                          onClick={() => changeUserRole(user.id, 'admin')}
                          className="flex-1 px-2 py-1 rounded bg-green-500/10 hover:bg-green-500/20 text-green-400 text-xs font-medium transition-all"
                        >
                          Promote
                        </button>
                      )}
                      {user.role !== 'customer' && (
                        <button
                          onClick={() => changeUserRole(user.id, 'customer')}
                          className="flex-1 px-2 py-1 rounded bg-slate-500/10 hover:bg-slate-500/20 text-slate-400 text-xs font-medium transition-all"
                        >
                          Demote
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}