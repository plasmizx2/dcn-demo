import { AdminLayout } from '../components/admin-layout';
import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, FileText, CheckCircle2, XCircle, Clock, Loader2, Download } from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../config';

interface Task {
  id: string;
  task_id: number;
  status: string;
  result?: any;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}

interface Job {
  id: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
  completed_at?: string;
  task_count: number;
  completed_tasks: number;
  failed_tasks: number;
}

export function ResultsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Record<string, Task[]>>({});
  const [loadingTasks, setLoadingTasks] = useState<string | null>(null);

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      const response = await apiFetch('jobs');
      if (response.ok) {
        const data = await response.json();
        setJobs(data);
      }
    } catch (error) {
      console.debug('Jobs endpoint not available');
    } finally {
      setLoading(false);
    }
  };

  const loadTasks = async (jobId: string) => {
    if (tasks[jobId]) return; // Already loaded

    setLoadingTasks(jobId);
    try {
      const response = await apiFetch(`jobs/${jobId}/tasks`);
      if (response.ok) {
        const data = await response.json();
        setTasks(prev => ({ ...prev, [jobId]: data }));
      } else {
        toast.error('Failed to load tasks');
      }
    } catch (error) {
      toast.error('Failed to load tasks');
    } finally {
      setLoadingTasks(null);
    }
  };

  const toggleJobDetails = (jobId: string) => {
    if (selectedJob === jobId) {
      setSelectedJob(null);
    } else {
      setSelectedJob(jobId);
      loadTasks(jobId);
    }
  };

  const exportResults = (job: Job) => {
    const jobTasks = tasks[job.id] || [];
    const results = {
      job: {
        id: job.id,
        title: job.title,
        description: job.description,
        status: job.status,
        created_at: job.created_at,
        completed_at: job.completed_at
      },
      tasks: jobTasks.map(t => ({
        task_id: t.task_id,
        status: t.status,
        result: t.result,
        error: t.error_message,
        completed_at: t.completed_at
      }))
    };

    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `job-${job.id}-results.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Results exported');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'failed': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'running': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'pending': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className="w-4 h-4" />;
      case 'failed': return <XCircle className="w-4 h-4" />;
      case 'running': return <Loader2 className="w-4 h-4 animate-spin" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="container mx-auto px-4 md:px-6 py-8 md:py-12">
          <div className="flex items-center justify-center py-20">
            <div className="text-slate-400">Loading results...</div>
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
            <h1 className="text-3xl md:text-4xl font-bold mb-3 text-white">Results</h1>
            <p className="text-slate-400 text-base md:text-lg">View and analyze job outputs</p>
          </div>

          {/* Summary stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {[
              { label: 'Total Jobs', value: jobs.length, color: 'purple' },
              { label: 'Completed', value: jobs.filter(j => j.status === 'completed').length, color: 'green' },
              { label: 'Running', value: jobs.filter(j => j.status === 'running').length, color: 'blue' },
              { label: 'Failed', value: jobs.filter(j => j.status === 'failed').length, color: 'red' }
            ].map((stat, i) => (
              <div key={i} className="p-4 md:p-6 rounded-xl bg-slate-900/40 backdrop-blur-xl border border-white/5">
                <div className={`text-2xl md:text-3xl font-bold bg-gradient-to-r from-${stat.color}-400 to-${stat.color}-600 bg-clip-text text-transparent mb-1`}>
                  {stat.value}
                </div>
                <div className="text-xs md:text-sm text-slate-400">{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Jobs list */}
          <div className="space-y-4">
            {jobs.map((job) => (
              <div key={job.id} className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden">
                {/* Job header */}
                <div className="p-4 md:p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-base md:text-lg font-semibold text-white truncate">{job.title}</h3>
                        <span className={`inline-flex items-center gap-1.5 px-2 md:px-3 py-1 rounded-lg text-xs font-medium border ${getStatusColor(job.status)}`}>
                          {getStatusIcon(job.status)}
                          {job.status}
                        </span>
                      </div>
                      <p className="text-xs md:text-sm text-slate-400 mb-3 line-clamp-2">{job.description}</p>
                      <div className="flex flex-wrap items-center gap-3 md:gap-4 text-xs text-slate-500">
                        <span>Created {new Date(job.created_at).toLocaleDateString()}</span>
                        {job.completed_at && <span>Completed {new Date(job.completed_at).toLocaleDateString()}</span>}
                        <span>{job.task_count} tasks</span>
                        <span className="text-green-400">{job.completed_tasks} completed</span>
                        {job.failed_tasks > 0 && <span className="text-red-400">{job.failed_tasks} failed</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {job.status === 'completed' && (
                        <button
                          onClick={() => exportResults(job)}
                          className="p-2 rounded-lg hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
                          title="Export results"
                        >
                          <Download className="w-4 h-4 md:w-5 md:h-5" />
                        </button>
                      )}
                      <button
                        onClick={() => toggleJobDetails(job.id)}
                        className="p-2 rounded-lg hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
                      >
                        {selectedJob === job.id ? <ChevronUp className="w-4 h-4 md:w-5 md:h-5" /> : <ChevronDown className="w-4 h-4 md:w-5 md:h-5" />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Task details */}
                <AnimatePresence>
                  {selectedJob === job.id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="border-t border-white/5 overflow-hidden"
                    >
                      <div className="p-4 md:p-6 bg-slate-800/30">
                        {loadingTasks === job.id ? (
                          <div className="flex items-center justify-center py-8 text-slate-400">
                            <Loader2 className="w-5 h-5 animate-spin mr-2" />
                            Loading tasks...
                          </div>
                        ) : tasks[job.id] && tasks[job.id].length > 0 ? (
                          <div className="space-y-3">
                            <h4 className="text-xs md:text-sm font-semibold text-white mb-4 flex items-center gap-2">
                              <FileText className="w-4 h-4 text-purple-400" />
                              Task Results ({tasks[job.id].length})
                            </h4>
                            <div className="grid gap-3 max-h-96 overflow-y-auto pr-2">
                              {tasks[job.id].map((task) => (
                                <div key={task.id} className="p-3 md:p-4 rounded-xl bg-slate-900/50 border border-white/5">
                                  <div className="flex items-start justify-between gap-3 mb-2">
                                    <div className="flex items-center gap-2">
                                      <span className="text-xs md:text-sm font-mono text-slate-500">Task #{task.task_id}</span>
                                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${getStatusColor(task.status)}`}>
                                        {getStatusIcon(task.status)}
                                        {task.status}
                                      </span>
                                    </div>
                                    {task.completed_at && (
                                      <span className="text-xs text-slate-500">
                                        {new Date(task.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                      </span>
                                    )}
                                  </div>
                                  
                                  {task.result && (
                                    <div className="mt-3 p-3 rounded-lg bg-slate-950/50 border border-white/5">
                                      <div className="text-xs text-slate-500 mb-2">Output:</div>
                                      <pre className="text-xs md:text-sm text-slate-300 whitespace-pre-wrap font-mono overflow-x-auto">
                                        {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                  
                                  {task.error_message && (
                                    <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                      <div className="text-xs text-red-400 mb-1">Error:</div>
                                      <pre className="text-xs md:text-sm text-red-300 whitespace-pre-wrap font-mono">
                                        {task.error_message}
                                      </pre>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-8 text-slate-400">
                            No tasks found
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}

            {jobs.length === 0 && (
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-12 text-center">
                <FileText className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400">No jobs found</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}