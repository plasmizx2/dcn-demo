import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useState, useEffect } from 'react';
import { CheckCircle2, Clock, XCircle, Loader2, ExternalLink, Download } from 'lucide-react';
import { toast } from 'sonner';
import { apiFetch } from '../config';

interface Job {
  id: string;
  title: string;
  task_type: string;
  status: string;
  created_at: string;
  final_output?: string;
}

interface Task {
  id: string;
  task_name: string;
  status: string;
}

export function MyJobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedJob) {
      loadTasks(selectedJob);
    }
  }, [selectedJob]);

  const loadJobs = async () => {
    try {
      const response = await apiFetch('jobs/mine');
      if (response.ok) {
        const data = await response.json();
        setJobs(data.sort((a: Job, b: Job) => 
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        ));
      }
    } catch (error) {
      console.debug('Jobs endpoint not available');
    } finally {
      setLoading(false);
    }
  };

  const loadTasks = async (jobId: string) => {
    try {
      const response = await apiFetch(`jobs/${jobId}/tasks`);
      if (response.ok) {
        const data = await response.json();
        setTasks(data);
      }
    } catch (error) {
      console.error('Failed to load tasks');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-400" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Clock className="w-5 h-5 text-yellow-400" />;
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

  const downloadExport = async (jobId: string, format: string) => {
    try {
      const response = await apiFetch(`/jobs/${jobId}/export?format=${format}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `job-${jobId}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success(`Downloaded as ${format.toUpperCase()}`);
      }
    } catch (error) {
      toast.error('Failed to download');
    }
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-screen">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8">
            <h1 className="text-4xl font-bold mb-3 text-white">My Jobs</h1>
            <p className="text-slate-400 text-lg">
              Track the status and results of your submitted jobs
            </p>
          </div>

          {jobs.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-16 h-16 rounded-full bg-slate-800/50 flex items-center justify-center mb-4">
                <Clock className="w-10 h-10 text-slate-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2 text-white">No jobs yet</h3>
              <p className="text-slate-400 mb-6">Submit your first job to get started</p>
              <a
                href="/submit"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 font-semibold hover:shadow-lg transition-all"
              >
                Submit a Job
              </a>
            </div>
          ) : (
            <div className="space-y-4">
              {jobs.map((job) => (
                <motion.div
                  key={job.id}
                  initial={{ y: 20, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 hover:border-white/20 transition-all overflow-hidden"
                >
                  <div 
                    className="p-6 cursor-pointer"
                    onClick={() => setSelectedJob(selectedJob === job.id ? null : job.id)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          {getStatusIcon(job.status)}
                          <h3 className="text-xl font-semibold text-white">{job.title}</h3>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-slate-400">
                          <span className="px-3 py-1 rounded-full bg-purple-500/10 text-purple-400 text-xs font-medium uppercase tracking-wide">
                            {job.task_type.replace(/_/g, ' ')}
                          </span>
                          <span>{new Date(job.created_at).toLocaleString()}</span>
                          <span className="text-slate-600">#{job.id.substring(0, 8)}</span>
                        </div>
                      </div>
                      <div className={`px-4 py-2 rounded-full border text-sm font-medium ${getStatusColor(job.status)}`}>
                        {job.status}
                      </div>
                    </div>
                  </div>

                  {selectedJob === job.id && (
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: 'auto' }}
                      className="border-t border-white/10 p-6 bg-slate-900/30"
                    >
                      <div className="mb-6">
                        <div className="flex items-center justify-between mb-4">
                          <h4 className="font-semibold text-lg text-white">Tasks ({tasks.length})</h4>
                          {job.status === 'completed' && (
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-slate-500 uppercase tracking-wider">Download</span>
                              <button
                                onClick={() => downloadExport(job.id, 'md')}
                                className="px-3 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-sm font-medium transition-colors"
                              >
                                Markdown
                              </button>
                              <button
                                onClick={() => downloadExport(job.id, 'json')}
                                className="px-3 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-sm font-medium transition-colors"
                              >
                                JSON
                              </button>
                              <button
                                onClick={() => downloadExport(job.id, 'csv')}
                                className="px-3 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 text-sm font-medium transition-colors"
                              >
                                CSV
                              </button>
                            </div>
                          )}
                        </div>
                        <div className="grid gap-2">
                          {tasks.map((task) => (
                            <div
                              key={task.id}
                              className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5"
                            >
                              <span className="text-sm text-slate-300">{task.task_name}</span>
                              <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                                {task.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {job.final_output && (
                        <div>
                          <h4 className="font-semibold text-lg mb-4 text-white">Final Output</h4>
                          <div className="max-h-96 overflow-y-auto p-4 rounded-xl bg-slate-950/50 border border-white/10 text-sm text-slate-300 font-mono whitespace-pre-wrap">
                            {job.final_output.substring(0, 2000)}
                            {job.final_output.length > 2000 && '...'}
                          </div>
                        </div>
                      )}
                    </motion.div>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </AdminLayout>
  );
}