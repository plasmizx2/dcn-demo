import { useNavigate } from 'react-router';
import { Check, Lock } from 'lucide-react';
import { motion } from 'motion/react';
import { useAuth } from '../hooks/use-auth';

export function PricingPage() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();

  const tiers = [
    {
      name: 'Free',
      price: '$0',
      period: '/month',
      description: 'Perfect for learning and small projects',
      cta: 'Get Started',
      featured: false,
      features: [
        '3 jobs per day',
        'Basic task decomposition',
        'Sequential execution',
        'Email support',
        'Community access',
      ],
    },
    {
      name: 'Pay-as-you-go',
      price: 'Custom',
      period: 'per job',
      description: 'For variable workloads',
      cta: 'Get Started',
      featured: false,
      features: [
        'Unlimited jobs',
        'Pay per compute second',
        'Distributed execution',
        'Real-time monitoring',
        'Priority queue',
        'Email support',
      ],
    },
    {
      name: 'Pro',
      price: '$5',
      period: '/month',
      description: 'For power users and teams',
      cta: 'Upgrade to Pro',
      featured: true,
      features: [
        'Unlimited jobs',
        'No per-job charges',
        'Distributed execution',
        'Real-time monitoring',
        'Higher queue priority',
        'Priority email support',
        'Advanced analytics',
        'API access',
      ],
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-950 text-white">
      {/* Header */}
      <div className="border-b border-slate-800">
        <nav className="flex items-center justify-between px-6 py-4 max-w-7xl mx-auto w-full">
          <div className="text-xl font-bold text-purple-400">DCN</div>
          <div className="flex gap-6">
            {user ? (
              <>
                <button
                  onClick={() => navigate('/submit')}
                  className="text-sm hover:text-purple-400 transition"
                >
                  Submit Job
                </button>
                <button
                  onClick={() => navigate('/account')}
                  className="text-sm hover:text-purple-400 transition"
                >
                  Account
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => navigate('/')}
                  className="text-sm hover:text-purple-400 transition"
                >
                  Back
                </button>
                <button
                  onClick={() => navigate('/login?next=/pricing')}
                  className="text-sm px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-semibold transition"
                >
                  Sign In
                </button>
              </>
            )}
          </div>
        </nav>
      </div>

      {/* Hero */}
      <div className="px-6 py-20 text-center max-w-7xl mx-auto">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-5xl font-bold mb-6"
        >
          Simple, Predictable Pricing
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-xl text-slate-300 mb-12"
        >
          Choose the plan that fits your workflow. Upgrade or downgrade anytime.
        </motion.p>
      </div>

      {/* Pricing Cards */}
      <div className="px-6 py-20 max-w-7xl mx-auto">
        <div className="grid md:grid-cols-3 gap-8">
          {tiers.map((tier, idx) => (
            <motion.div
              key={tier.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              className={`rounded-lg border p-8 relative ${
                tier.featured
                  ? 'border-purple-500 bg-gradient-to-br from-purple-900/20 to-transparent ring-2 ring-purple-500'
                  : 'border-slate-700 bg-slate-800/50 hover:border-slate-600 transition'
              }`}
            >
              {tier.featured && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="bg-purple-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="mb-8">
                <h3 className="text-2xl font-bold mb-2">{tier.name}</h3>
                <p className="text-slate-400 text-sm">{tier.description}</p>
              </div>

              <div className="mb-6">
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold">{tier.price}</span>
                  <span className="text-slate-400">{tier.period}</span>
                </div>
              </div>

              <button
                onClick={() => {
                  if (!user) {
                    // Redirect to login, then back to pricing so they can complete the purchase
                    navigate('/login?next=/pricing');
                  } else {
                    navigate('/account');
                  }
                }}
                disabled={loading}
                className={`w-full py-3 rounded-lg font-semibold mb-8 transition flex items-center justify-center gap-2 ${
                  tier.featured
                    ? 'bg-purple-600 hover:bg-purple-700 text-white'
                    : 'bg-slate-700 hover:bg-slate-600 text-white'
                } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {!user && !loading && <Lock className="w-4 h-4" />}
                {loading ? 'Loading...' : user ? tier.cta : `Sign in to ${tier.name === 'Free' ? 'start' : 'buy'}`}
              </button>

              <div className="space-y-3">
                {tier.features.map((feature) => (
                  <div key={feature} className="flex gap-3 items-start">
                    <Check className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                    <span className="text-slate-300">{feature}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* FAQ Section */}
      <div className="px-6 py-20 max-w-3xl mx-auto">
        <h2 className="text-3xl font-bold mb-12 text-center">Questions?</h2>
        <div className="space-y-8">
          <div>
            <h3 className="text-xl font-semibold mb-2">Can I change plans anytime?</h3>
            <p className="text-slate-400">
              Yes! Upgrade or downgrade your plan at any time from your account settings. Changes take effect immediately.
            </p>
          </div>
          <div>
            <h3 className="text-xl font-semibold mb-2">What's included with distributed execution?</h3>
            <p className="text-slate-400">
              Our distributed system automatically decomposes your tasks and runs them in parallel across multiple workers, typically delivering 3-5x speedup compared to sequential execution.
            </p>
          </div>
          <div>
            <h3 className="text-xl font-semibold mb-2">Is there a free trial for Pro?</h3>
            <p className="text-slate-400">
              Start with Free tier and upgrade to Pro whenever you're ready. You'll only be charged after you upgrade.
            </p>
          </div>
          <div>
            <h3 className="text-xl font-semibold mb-2">What happens to my data if I downgrade?</h3>
            <p className="text-slate-400">
              All your job history and results are preserved. Downgrading only affects your future job limits and features.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
