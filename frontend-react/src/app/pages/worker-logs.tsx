import { AdminLayout } from '../components/admin-layout';
import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { Cpu, Activity, Clock, ChevronDown, ChevronUp, CheckCircle2, XCircle, AlertCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

interface Worker {
  worker_id: string;
  status: string;
  last_heartbeat: string;
  tasks_completed: number;
  tasks_failed: number;
  uptime_seconds: number;
}

interface WorkerHistory {
  task_id: string;
  job_id: string;
  job_title?: string;
  status: string;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  duration_seconds?: number;
}

export function WorkerLogsPage() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedWorker, setSelectedWorker] = useState<string | null>(null);
  const [workerHistory, setWorkerHistory] = useState<Record<string, WorkerHistory[]>>({});
  const [loadingHistory, setLoadingHistory] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<any>(null);

  useEffect(() => {
    // Get current user to check if admin
    fetch('/auth/me', { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(u => setCurrentUser(u))
      .catch(() => {});

    loadWorkers();
    
    // Auto-refresh every 10 seconds
    const interval = setInterval(loadWorkers, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadWorkers = async () => {
    try {
      const response = await fetch('/monitor/workers', { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setWorkers(data);
      } else {
        toast.error('Failed to load workers');
      }
    } catch (error) {
      console.error('Failed to load workers', error);
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async (workerId: string) => {
    if (workerHistory[workerId]) return; // Already loaded

    setLoadingHistory(workerId);
    try {
      const response = await fetch(`/monitor/worker-history/${workerId}`, { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setWorkerHistory(prev => ({ ...prev, [workerId]: data }));
      } else {
        toast.error('Failed to load worker history');
      }
    } catch (error) {
      toast.error('Failed to load worker history');
    } finally {
      setLoadingHistory(null);
    }
  };

  const deleteWorker = async (workerId: string) => {
    if (!window.confirm(`Are you sure you want to delete worker ${workerId}?`)) return;

    try {
      const response = await fetch(`/monitor/workers/${workerId}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (response.ok) {
        toast.success('Worker deleted');
        loadWorkers();
      } else {
        toast.error('Failed to delete worker');
      }
    } catch (error) {
      toast.error('Failed to delete worker');
    }
  };

  const toggleWorkerDetails = (workerId: string) => {
    if (selectedWorker === workerId) {
      setSelectedWorker(null);
    } else {
      setSelectedWorker(workerId);
      loadHistory(workerId);
    }
  };

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const getWorkerStatus = (worker: Worker) => {
    const lastHeartbeat = new Date(worker.last_heartbeat);
    const now = new Date();
    const secondsSinceHeartbeat = (now.getTime() - lastHeartbeat.getTime()) / 1000;
    
    if (secondsSinceHeartbeat < 60) return { label: 'Online', color: 'green' };
    if (secondsSinceHeartbeat < 300) return { label: 'Idle', color: 'yellow' };
    return { label: 'Offline', color: 'red' };
  };

  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'ceo';

  if (loading) {
    return (
      <AdminLayout>
        <div className="container mx-auto px-4 md:px-6 py-8 md:py-12">
          <div className="flex items-center justify-center py-20">
            <div className="text-slate-400">Loading workers...</div>
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
            <h1 className="text-3xl md:text-4xl font-bold mb-3 text-white">Worker Logs</h1>
            <p className="text-slate-400 text-base md:text-lg">Monitor worker nodes and task history</p>
          </div>

          {/* Worker stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {[
              { label: 'Total Workers', value: workers.length, color: 'purple' },
              { label: 'Online', value: workers.filter(w => getWorkerStatus(w).label === 'Online').length, color: 'green' },
              { label: 'Idle', value: workers.filter(w => getWorkerStatus(w).label === 'Idle').length, color: 'yellow' },
              { label: 'Offline', value: workers.filter(w => getWorkerStatus(w).label === 'Offline').length, color: 'red' }
            ].map((stat, i) => (
              <div key={i} className="p-4 md:p-6 rounded-xl bg-slate-900/40 backdrop-blur-xl border border-white/5">
                <div className={`text-2xl md:text-3xl font-bold bg-gradient-to-r from-${stat.color}-400 to-${stat.color}-600 bg-clip-text text-transparent mb-1`}>
                  {stat.value}
                </div>
                <div className="text-xs md:text-sm text-slate-400">{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Workers list */}
          <div className="space-y-4">
            {workers.map((worker) => {
              const status = getWorkerStatus(worker);
              return (
                <div key={worker.worker_id} className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
                  {/* Worker header */}
                  <div className="p-4 md:p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-3 md:gap-4 flex-1 min-w-0">
                        <div className={`w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br ${
                          status.color === 'green' ? 'from-green-500 to-emerald-500' :
                          status.color === 'yellow' ? 'from-yellow-500 to-orange-500' :
                          'from-red-500 to-rose-500'
                        } flex items-center justify-center shadow-lg flex-shrink-0`}>
                          <Cpu className="w-5 h-5 md:w-6 md:h-6 text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-sm md:text-base font-semibold text-white font-mono truncate">{worker.worker_id}</h3>
                            <span className={`px-2 py-0.5 rounded-lg text-xs font-medium ${
                              status.color === 'green' ? 'bg-green-500/20 text-green-400' :
                              status.color === 'yellow' ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-red-500/20 text-red-400'
                            }`}>
                              {status.label}
                            </span>
                          </div>
                          <div className="flex flex-wrap items-center gap-3 md:gap-4 text-xs text-slate-500">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              Uptime: {formatUptime(worker.uptime_seconds)}
                            </span>
                            <span className="text-green-400">{worker.tasks_completed} completed</span>
                            {worker.tasks_failed > 0 && <span className="text-red-400">{worker.tasks_failed} failed</span>}
                            <span>Last seen: {new Date(worker.last_heartbeat).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isAdmin && (
                          <button
                            onClick={() => deleteWorker(worker.worker_id)}
                            className="p-2 rounded-lg hover:bg-red-500/10 transition-colors text-slate-400 hover:text-red-400"
                            title="Delete worker"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => toggleWorkerDetails(worker.worker_id)}
                          className="p-2 rounded-lg hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
                        >
                          {selectedWorker === worker.worker_id ? <ChevronUp className="w-4 h-4 md:w-5 md:h-5" /> : <ChevronDown className="w-4 h-4 md:w-5 md:h-5" />}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Worker history */}
                  <AnimatePresence>
                    {selectedWorker === worker.worker_id && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className="border-t border-white/5 overflow-hidden"
                      >
                        <div className="p-4 md:p-6 bg-slate-800/30">
                          {loadingHistory === worker.worker_id ? (
                            <div className="flex items-center justify-center py-8 text-slate-400">
                              Loading history...
                            </div>
                          ) : workerHistory[worker.worker_id] && workerHistory[worker.worker_id].length > 0 ? (
                            <div className="space-y-3">
                              <h4 className="text-xs md:text-sm font-semibold text-white mb-4 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-purple-400" />
                                Task History ({workerHistory[worker.worker_id].length})
                              </h4>
                              <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
                                {workerHistory[worker.worker_id].map((task, idx) => (
                                  <div key={idx} className="p-3 rounded-xl bg-slate-900/50 border border-white/5">
                                    <div className="flex items-start justify-between gap-3 mb-2">
                                      <div className="flex items-center gap-2">
                                        {task.status === 'completed' ? (
                                          <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                                        ) : task.status === 'failed' ? (
                                          <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                                        ) : (
                                          <AlertCircle className="w-4 h-4 text-yellow-400 flex-shrink-0" />
                                        )}
                                        <div className="min-w-0">
                                          <div className="text-xs md:text-sm text-white">
                                            {task.job_title || `Job ${task.job_id}`} - Task #{task.task_id}
                                          </div>
                                          <div className="text-xs text-slate-500">
                                            Started: {new Date(task.started_at).toLocaleString()}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="text-right flex-shrink-0">
                                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                          task.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                                          task.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                                          'bg-yellow-500/20 text-yellow-400'
                                        }`}>
                                          {task.status}
                                        </span>
                                        {task.duration_seconds !== undefined && (
                                          <div className="text-xs text-slate-500 mt-1">
                                            {task.duration_seconds}s
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                    {task.error_message && (
                                      <div className="mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                                        <div className="text-xs text-red-300 font-mono">{task.error_message}</div>
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <div className="text-center py-8 text-slate-400">
                              No task history found
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}

            {workers.length === 0 && (
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-12 text-center">
                <Cpu className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400">No workers found</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}