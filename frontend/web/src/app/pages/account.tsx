import { AdminLayout } from '../components/admin-layout';
import { TierBadge } from '../components/stripe-payment';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { Loader2, CreditCard, Crown, Zap, CheckCircle2, AlertCircle, ArrowRight, Wallet, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { useRequireAuth } from '../hooks/use-require-auth';

type TierInfo = {
  tier: string;
  has_payment_method: boolean;
  has_subscription: boolean;
};

type Payment = {
  id: string;
  job_id: string;
  amount_cents: number;
  status: string;
  created_at: string;
  job_title?: string;
};

type BalanceTransaction = {
  id: string;
  description: string;
  amount_cents: number;
  balance_after_cents: number;
  created_at: string;
};

const money = (cents: number) =>
  new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(cents / 100);

export function AccountPage() {
  const { ready } = useRequireAuth();
  const [tierInfo, setTierInfo] = useState<TierInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [upgrading, setUpgrading] = useState(false);
  const [balance, setBalance] = useState<number>(0);
  const [transactions, setTransactions] = useState<BalanceTransaction[]>([]);
  const [toppingUp, setToppingUp] = useState(false);

  const fetchBalance = async () => {
    try {
      const res = await fetch("/billing/balance", { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setBalance(data.balance_cents ?? 0);
      }
    } catch {
      // ignore
    }
  };

  const fetchTransactions = async () => {
    try {
      const res = await fetch("/billing/balance/history", { credentials: "include" });
      if (res.ok) {
        const data: BalanceTransaction[] = await res.json();
        setTransactions(data);
      }
    } catch {
      // ignore
    }
  };

  // Check URL params for success — verify topup or pro upgrade via backend
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");

    if (params.get("topup") === "success" && sessionId) {
      fetch("/billing/verify-topup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.credited) {
            toast.success(`Balance topped up by ${money(data.amount_cents)}!`);
          } else if (data.reason === "already_credited") {
            toast.success("Balance already credited!");
          } else {
            toast.error("Could not verify payment. It may take a moment.");
          }
          fetchBalance();
          fetchTransactions();
        })
        .catch(() => toast.error("Could not verify payment"));
    } else if (params.get("upgrade") === "success" && sessionId) {
      fetch("/billing/verify-pro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.activated) {
            toast.success("Welcome to Pro! Unlimited jobs, faster queue priority.");
          } else if (data.reason === "already_activated") {
            toast.success("Pro tier already active!");
          } else {
            toast.error("Could not activate Pro. It may take a moment.");
          }
          // Re-fetch tier to update UI
          fetch("/billing/tier", { credentials: "include" })
            .then((r) => r.json())
            .then((data) => setTierInfo(data));
        })
        .catch(() => toast.error("Could not verify Pro upgrade"));
    }

    // Clean up the URL
    if (params.has("topup") || params.has("upgrade")) {
      const url = new URL(window.location.href);
      url.searchParams.delete("topup");
      url.searchParams.delete("upgrade");
      url.searchParams.delete("session_id");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    (async () => {
      try {
        // Fetch tier info
        const tierRes = await fetch('/billing/tier', { credentials: 'include' });
        if (tierRes.ok) {
          const data: TierInfo = await tierRes.json();
          setTierInfo(data);
        }

        // Fetch payment history (could use user ID in real app)
        const paymentsRes = await fetch('/billing/admin/payments', { credentials: 'include' });
        if (paymentsRes.ok) {
          const data: Payment[] = await paymentsRes.json();
          setPayments(data.slice(0, 10)); // Last 10 payments
        }

        // Fetch balance and transaction history
        await fetchBalance();
        await fetchTransactions();
      } catch (e) {
        console.error('Failed to fetch account data:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, [ready]);

  const handleTopUp = async (amountCents: number) => {
    setToppingUp(true);
    try {
      const res = await fetch("/billing/topup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ amount_cents: amountCents }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || "Top-up failed");
      }
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Top-up failed");
    } finally {
      setToppingUp(false);
    }
  };

  const handleUpgrade = async (tier: string) => {
    setUpgrading(true);
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
        window.location.href = data.checkout_url;
        return;
      }

      setTierInfo((prev) => (prev ? { ...prev, tier: data.tier || tier } : null));
      toast.success(`Switched to ${tier} tier`);
    } catch (e) {
      toast.error('Failed to change tier');
    } finally {
      setUpgrading(false);
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

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-4xl">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-12">
            <h1 className="text-4xl font-bold mb-2 text-white">Account Settings</h1>
            <p className="text-slate-400">Manage your subscription, billing, and preferences</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Main content */}
            <div className="md:col-span-2 space-y-6">
              {/* Balance card — shown for paygo users */}
              {tierInfo && tierInfo.tier === "paygo" && (
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
                  <div className="flex items-center gap-2 mb-6">
                    <Wallet className="w-6 h-6 text-emerald-400" />
                    <h2 className="text-2xl font-bold text-white">Balance</h2>
                  </div>
                  <p className="text-4xl font-bold tracking-tight text-white tabular-nums mb-6">
                    {money(balance)}
                  </p>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-400 mr-1">Top up:</span>
                    {[
                      { label: "$5", cents: 500 },
                      { label: "$10", cents: 1000 },
                      { label: "$20", cents: 2000 },
                    ].map(({ label, cents }) => (
                      <button
                        key={cents}
                        onClick={() => handleTopUp(cents)}
                        disabled={toppingUp}
                        className="px-4 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 transition-all text-sm font-semibold flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Current plan */}
              {tierInfo && (
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
                  <h2 className="text-2xl font-bold text-white mb-6">Current Plan</h2>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-slate-400 mb-2">Your Tier</label>
                      <div className="flex items-center gap-3">
                        <TierBadge tier={tierInfo.tier} />
                        <p className="text-lg font-semibold text-white">
                          {tierInfo.tier === 'free'
                            ? 'Free — 3 jobs/day'
                            : tierInfo.tier === 'paygo'
                              ? 'Pay-as-you-go — per-job pricing'
                              : 'Pro — $5/month, unlimited jobs'}
                        </p>
                      </div>
                    </div>

                    {tierInfo.tier === 'pro' && tierInfo.has_subscription && (
                      <div className="pt-4 border-t border-white/10">
                        <button
                          onClick={() => {
                            if (
                              confirm(
                                "Are you sure? You'll be downgraded to Free tier (3 jobs/day).",
                              )
                            ) {
                              handleUpgrade('free');
                            }
                          }}
                          className="px-4 py-2 rounded-lg border border-red-500/50 text-red-400 hover:bg-red-500/10 transition-all text-sm font-medium"
                        >
                          Cancel Subscription
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Payment history */}
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
                <h2 className="text-2xl font-bold text-white mb-6">Payment History</h2>
                {payments.length > 0 ? (
                  <div className="space-y-3">
                    {payments.map((p) => (
                      <div
                        key={p.id}
                        className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/10"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-white truncate">
                            {p.job_title || `Job ${p.job_id?.substring(0, 8) || 'N/A'}`}
                          </p>
                          <p className="text-xs text-slate-400">
                            {new Date(p.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="text-right ml-4">
                          <p className="font-semibold text-white">{money(p.amount_cents)}</p>
                          <p
                            className={`text-xs ${
                              p.status === 'captured'
                                ? 'text-green-400'
                                : p.status === 'authorized'
                                  ? 'text-blue-400'
                                  : 'text-amber-400'
                            }`}
                          >
                            {p.status}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-400">No payments yet</p>
                )}
              </div>

              {/* Balance History */}
              {tierInfo && tierInfo.tier === "paygo" && (
                <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-8">
                  <h2 className="text-2xl font-bold text-white mb-6">Balance History</h2>
                  {transactions.length > 0 ? (
                    <div className="space-y-3">
                      {transactions.map((t) => (
                        <div
                          key={t.id}
                          className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/10"
                        >
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-white truncate">
                              {t.description}
                            </p>
                            <p className="text-xs text-slate-400">
                              {new Date(t.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <div className="text-right ml-4">
                            <p
                              className={`font-semibold ${
                                t.amount_cents >= 0 ? "text-green-400" : "text-red-400"
                              }`}
                            >
                              {t.amount_cents >= 0 ? "+" : ""}{money(t.amount_cents)}
                            </p>
                            <p className="text-xs text-slate-400">
                              Balance: {money(t.balance_after_cents)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-slate-400">No transactions yet</p>
                  )}
                </div>
              )}
            </div>

            {/* Sidebar: upgrade options */}
            <div className="space-y-6">
              <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                <h3 className="font-bold text-white mb-4">Change Plan</h3>
                <div className="space-y-2">
                  {[
                    { id: 'free', label: 'Free', desc: '3 jobs/day', icon: Zap, color: 'slate' },
                    {
                      id: 'paygo',
                      label: 'Pay-as-you-go',
                      desc: 'Per-job pricing',
                      icon: CreditCard,
                      color: 'blue',
                    },
                    { id: 'pro', label: 'Pro — $5/mo', desc: 'Unlimited', icon: Crown, color: 'purple' },
                  ].map(({ id, label, desc, icon: Icon, color }) => (
                    <button
                      key={id}
                      onClick={() => id !== tierInfo?.tier && handleUpgrade(id)}
                      disabled={upgrading || id === tierInfo?.tier}
                      className={`w-full text-left px-3 py-2.5 rounded-xl border transition-all flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed ${
                        tierInfo?.tier === id
                          ? `bg-${color}-500/15 border-${color}-500/40 text-white`
                          : 'border-white/5 text-slate-400 hover:border-white/15 hover:text-slate-200'
                      }`}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium">{label}</div>
                        <div className="text-xs opacity-60">{desc}</div>
                      </div>
                      {tierInfo?.tier === id && <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* Info boxes */}
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-2xl p-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-blue-300 mb-1">Free tier limits</h4>
                    <p className="text-sm text-slate-300">3 jobs per day. Upgrade for unlimited access.</p>
                  </div>
                </div>
              </div>

              <div className="bg-green-500/10 border border-green-500/30 rounded-2xl p-6">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-green-300 mb-1">Pro includes</h4>
                    <p className="text-sm text-slate-300">Unlimited jobs, higher queue priority, no per-job fees.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
