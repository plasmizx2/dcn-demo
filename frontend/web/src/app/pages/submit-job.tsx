import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';
import { useState } from 'react';
import { Sparkles, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

export function SubmitJobPage() {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [taskType, setTaskType] = useState('ml_experiment');
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title.trim() || !description.trim()) {
      toast.error('Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          title,
          description,
          task_type: taskType,
          input_payload: {},
        })
      });

      if (!response.ok) {
        throw new Error('Failed to submit job');
      }

      const data = await response.json();
      setJobId(data.job_id || data.id);
      toast.success('Job submitted successfully!');
      
      // Reset form
      setTitle('');
      setDescription('');
    } catch (error) {
      toast.error('Failed to submit job. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-4xl">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8">
            <h1 className="text-4xl font-bold mb-3">Submit a Job</h1>
            <p className="text-slate-400 text-lg">
              Describe your task and let DCN handle the distributed execution
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Form */}
            <div className="md:col-span-2">
              <form onSubmit={handleSubmit} className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
                {jobId && (
                  <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="mb-6 p-4 rounded-xl bg-green-500/10 border border-green-500/30 flex items-start gap-3"
                  >
                    <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-green-400 font-semibold mb-1">Job submitted successfully!</p>
                      <p className="text-sm text-slate-400">
                        Job ID: <code className="text-green-400 font-mono">{jobId}</code>
                      </p>
                    </div>
                  </motion.div>
                )}

                <div className="space-y-6">
                  {/* Title */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Job Title
                    </label>
                    <input
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g., Compare ML models on dataset X"
                      className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500"
                      disabled={loading}
                    />
                  </div>

                  {/* Task Type */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Task Type
                    </label>
                    <select
                      value={taskType}
                      onChange={(e) => setTaskType(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white"
                      disabled={loading}
                    >
                      <option value="ml_experiment">ML Experiment</option>
                    </select>
                    <p className="mt-2 text-xs text-slate-500">
                      More task types ship when planners are enabled server-side.
                    </p>
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Description
                    </label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Describe your task in detail. What do you want to accomplish? The AI will plan and distribute the workload automatically."
                      rows={8}
                      className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all text-white placeholder:text-slate-500 resize-none"
                      disabled={loading}
                    />
                    <p className="mt-2 text-xs text-slate-500">
                      The more detail you provide, the better DCN can plan your job
                    </p>
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full px-6 py-4 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:from-purple-500/50 disabled:to-blue-500/50 text-white font-semibold shadow-lg shadow-purple-500/50 transition-all flex items-center justify-center gap-2 disabled:cursor-not-allowed"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Submitting...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-5 h-5" />
                        Submit Job
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>

            {/* Sidebar Info */}
            <div className="space-y-6">
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="w-5 h-5 text-purple-400" />
                  <h3 className="font-semibold">How it works</h3>
                </div>
                <ol className="space-y-3 text-sm text-slate-400">
                  <li className="flex gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold">
                      1
                    </span>
                    <span>AI analyzes your description</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold">
                      2
                    </span>
                    <span>Tasks are split across workers</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold">
                      3
                    </span>
                    <span>Parallel execution begins</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold">
                      4
                    </span>
                    <span>Results are aggregated</span>
                  </li>
                </ol>
              </div>

              <div className="bg-blue-500/10 border border-blue-500/30 rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle className="w-5 h-5 text-blue-400" />
                  <h3 className="font-semibold text-blue-400">Pro Tip</h3>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">
                  Be specific about your dataset, models, and expected outputs. The AI uses this to optimize task distribution.
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
