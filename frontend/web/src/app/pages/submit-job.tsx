import { AdminLayout } from '../components/admin-layout';
import {
  DatasetSourceSection,
  buildJobInputPayload,
  type DatasetMode,
} from '../components/dataset-source-section';
import { StripePaymentModal, TierBadge } from '../components/stripe-payment';
import { motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { Sparkles, Loader2, CheckCircle2, AlertCircle, Wallet, CreditCard, Zap, Crown } from 'lucide-react';
import { toast } from 'sonner';
import { useRequireAuth } from '../hooks/use-require-auth';

type CostEstimate = {
  subtask_count: number;
  compute_cost: number;
  platform_fee: number;
  platform_fee_percent: number;
  estimated_total: number;
};

type TierInfo = {
  tier: string;
  has_payment_method: boolean;
  has_subscription: boolean;
};

const money = (n: number) =>
  new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(n);

export function SubmitJobPage() {
  const { ready } = useRequireAuth();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [taskType, setTaskType] = useState('ml_experiment');
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [estLoading, setEstLoading] = useState(true);
  const [estError, setEstError] = useState<string | null>(null);

  const [datasetMode, setDatasetMode] = useState<DatasetMode>('built_in');
  const [builtInName, setBuiltInName] = useState('weather_ri');
  const [openmlId, setOpenmlId] = useState('');
  const [csvUrl, setCsvUrl] = useState('');
  const [uploadToken, setUploadToken] = useState<string | null>(null);
  const [targetOverride, setTargetOverride] = useState('');

  // Billing state
  const [tierInfo, setTierInfo] = useState<TierInfo | null>(null);
  const [showPayment, setShowPayment] = useState(false);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [paymentIntentId, setPaymentIntentId] = useState<string | null>(null);

  const inputPayload = useMemo(
    () =>
      buildJobInputPayload(datasetMode, builtInName, openmlId, csvUrl, uploadToken, targetOverride),
    [datasetMode, builtInName, openmlId, csvUrl, uploadToken, targetOverride],
  );

  // Fetch user tier on mount
  useEffect(() => {
    if (!ready) return;
    fetch('/billing/tier', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: TierInfo | null) => {
        if (data) setTierInfo(data);
      })
      .catch(() => {});
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setEstLoading(true);
    const t = setTimeout(() => {
      (async () => {
        setEstError(null);
        try {
          const res = await fetch('/jobs/estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
              title: title.trim() || 'Preview',
              description: description || '',
              task_type: taskType,
              input_payload: inputPayload,
            }),
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            const detail = (err as { detail?: unknown }).detail;
            const msg =
              typeof detail === 'string'
                ? detail
                : Array.isArray(detail)
                  ? JSON.stringify(detail)
                  : 'Could not estimate cost';
            throw new Error(msg);
          }
          const data: CostEstimate = await res.json();
          if (!cancelled) setEstimate(data);
        } catch (e) {
          if (!cancelled) {
            setEstimate(null);
            setEstError(e instanceof Error ? e.message : 'Estimate failed');
          }
        } finally {
          if (!cancelled) setEstLoading(false);
        }
      })();
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [ready, title, description, taskType, inputPayload]);

  const validateForm = (): boolean => {
    if (!title.trim() || !description.trim()) {
      toast.error('Please fill in all fields');
      return false;
    }
    if (datasetMode === 'openml' && !openmlId.trim()) {
      toast.error('Enter an OpenML dataset ID');
      return false;
    }
    if (datasetMode === 'csv_url' && !csvUrl.trim()) {
      toast.error('Enter a CSV URL');
      return false;
    }
    if (datasetMode === 'csv_upload' && !uploadToken) {
      toast.error('Upload a CSV file');
      return false;
    }
    return true;
  };

  const submitJob = async (piId?: string) => {
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
          input_payload: inputPayload,
          ...(piId ? { payment_intent_id: piId } : {}),
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const detail = (err as { detail?: string }).detail;
        throw new Error(detail || 'Failed to submit job');
      }

      const data = await response.json();
      setJobId(data.job_id || data.id);
      toast.success('Job submitted successfully!');
      setTitle('');
      setDescription('');
      setShowPayment(false);
      setClientSecret(null);
      setPaymentIntentId(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to submit job');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    const tier = tierInfo?.tier || 'free';

    if (tier === 'paygo') {
      // Create payment intent first, then show Stripe Elements
      setLoading(true);
      try {
        const res = await fetch('/billing/create-payment-intent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ task_type: taskType, input_payload: inputPayload }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as { detail?: string }).detail || 'Failed to create payment');
        }
        const data = await res.json();
        setClientSecret(data.client_secret);
        setPaymentIntentId(data.payment_intent_id);
        setShowPayment(true);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Payment setup failed');
      } finally {
        setLoading(false);
      }
      return;
    }

    // Free tier or Pro tier — submit directly
    await submitJob();
  };

  const handlePaymentSuccess = async (piId: string) => {
    await submitJob(piId);
  };

  const handleUpgrade = async (tier: string) => {
    try {
      const res = await fetch('/billing/upgrade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ tier }),
      });
      if (!res.ok) throw new Error('Upgrade failed');
      const data = await res.json();

      if (data.checkout_url) {
        // Pro subscription — redirect to Stripe Checkout
        window.location.href = data.checkout_url;
        return;
      }

      setTierInfo((prev) => (prev ? { ...prev, tier: data.tier || tier } : null));
      toast.success(`Switched to ${tier} tier`);
    } catch {
      toast.error('Failed to change tier');
    }
  };

  if (!ready) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[50vh]">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-4xl">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-3">
              <h1 className="text-4xl font-bold text-white">Submit a Job</h1>
              {tierInfo && <TierBadge tier={tierInfo.tier} />}
            </div>
            <p className="text-slate-400 text-lg">
              Describe your task and let DCN handle the distributed execution
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Form */}
            <div className="md:col-span-2">
              {/* Payment modal overlay */}
              {showPayment && clientSecret && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-6 bg-slate-900/80 backdrop-blur-xl rounded-2xl border border-purple-500/30 p-6"
                >
                  <div className="flex items-center gap-2 mb-4">
                    <CreditCard className="w-5 h-5 text-purple-400" />
                    <h3 className="font-semibold text-white">Payment required</h3>
                    <span className="ml-auto text-sm text-slate-400">
                      {estimate ? money(estimate.estimated_total) : ''}
                    </span>
                  </div>
                  <StripePaymentModal
                    clientSecret={clientSecret}
                    onSuccess={handlePaymentSuccess}
                    onCancel={() => {
                      setShowPayment(false);
                      setClientSecret(null);
                    }}
                  />
                </motion.div>
              )}

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
                      disabled={loading || showPayment}
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
                      disabled={loading || showPayment}
                    >
                      <option value="ml_experiment">ML Experiment</option>
                    </select>
                    <p className="mt-2 text-xs text-slate-500">
                      More task types ship when planners are enabled server-side.
                    </p>
                  </div>

                  <DatasetSourceSection
                    disabled={loading || showPayment}
                    mode={datasetMode}
                    onModeChange={(m) => {
                      setDatasetMode(m);
                      if (m !== 'csv_upload') setUploadToken(null);
                    }}
                    builtInName={builtInName}
                    onBuiltInNameChange={setBuiltInName}
                    openmlId={openmlId}
                    onOpenmlIdChange={setOpenmlId}
                    csvUrl={csvUrl}
                    onCsvUrlChange={setCsvUrl}
                    uploadToken={uploadToken}
                    onUploadTokenChange={setUploadToken}
                    targetOverride={targetOverride}
                    onTargetOverrideChange={setTargetOverride}
                  />

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
                      disabled={loading || showPayment}
                    />
                    <p className="mt-2 text-xs text-slate-500">
                      The more detail you provide, the better DCN can plan your job
                    </p>
                  </div>

                  {/* Submit Button */}
                  {!showPayment && (
                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full px-6 py-4 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:from-purple-500/50 disabled:to-blue-500/50 text-white font-semibold shadow-lg shadow-purple-500/50 transition-all flex items-center justify-center gap-2 disabled:cursor-not-allowed"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          {tierInfo?.tier === 'paygo' ? 'Setting up payment...' : 'Submitting...'}
                        </>
                      ) : (
                        <>
                          {tierInfo?.tier === 'paygo' ? (
                            <CreditCard className="w-5 h-5" />
                          ) : (
                            <Sparkles className="w-5 h-5" />
                          )}
                          {tierInfo?.tier === 'paygo' ? 'Pay & Submit' : 'Submit Job'}
                        </>
                      )}
                    </button>
                  )}
                </div>
              </form>
            </div>

            {/* Sidebar Info */}
            <div className="space-y-6">
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                <div className="flex items-center gap-2 mb-3">
                  <Wallet className="w-5 h-5 text-emerald-400" />
                  <h3 className="font-semibold text-white">Estimated cost</h3>
                </div>
                {estLoading ? (
                  <div className="h-16 rounded-lg bg-white/5 animate-pulse" aria-hidden />
                ) : estError ? (
                  <p className="text-sm text-amber-400/90">{estError}</p>
                ) : estimate ? (
                  <div className="space-y-2">
                    <p className="text-3xl font-bold tracking-tight text-white tabular-nums">
                      {tierInfo?.tier === 'pro' ? (
                        <span className="text-purple-400">Included</span>
                      ) : tierInfo?.tier === 'free' ? (
                        <span className="text-green-400">Free</span>
                      ) : (
                        money(estimate.estimated_total)
                      )}
                    </p>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {estimate.subtask_count} planned tasks · {money(estimate.compute_cost)} compute +{' '}
                      {estimate.platform_fee_percent}% fee ({money(estimate.platform_fee)})
                    </p>
                    {tierInfo?.tier === 'free' && (
                      <p className="text-xs text-emerald-400">
                        Free tier: 3 jobs/day
                      </p>
                    )}
                    {tierInfo?.tier === 'pro' && (
                      <p className="text-xs text-purple-400">
                        Pro: unlimited jobs, no per-job fees
                      </p>
                    )}
                  </div>
                ) : null}
              </div>

              {/* Tier selector */}
              {tierInfo && (
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                  <h3 className="font-semibold text-white mb-3">Your plan</h3>
                  <div className="space-y-2">
                    {[
                      { id: 'free', label: 'Free', desc: '3 jobs/day', icon: Zap, color: 'slate' },
                      { id: 'paygo', label: 'Pay-as-you-go', desc: 'Per-job pricing', icon: CreditCard, color: 'blue' },
                      { id: 'pro', label: 'Pro — $5/mo', desc: 'Unlimited + priority', icon: Crown, color: 'purple' },
                    ].map(({ id, label, desc, icon: Icon, color }) => (
                      <button
                        key={id}
                        onClick={() => id !== tierInfo.tier && handleUpgrade(id)}
                        className={`w-full text-left px-3 py-2.5 rounded-xl border transition-all flex items-center gap-3 ${
                          tierInfo.tier === id
                            ? `bg-${color}-500/15 border-${color}-500/40 text-white`
                            : 'border-white/5 text-slate-400 hover:border-white/15 hover:text-slate-200'
                        }`}
                      >
                        <Icon className="w-4 h-4 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium">{label}</div>
                          <div className="text-xs opacity-60">{desc}</div>
                        </div>
                        {tierInfo.tier === id && (
                          <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="w-5 h-5 text-purple-400" />
                  <h3 className="font-semibold text-white">How it works</h3>
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
                  <h3 className="font-semibold text-blue-300">Pro Tip</h3>
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
