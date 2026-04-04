import { useState, useEffect } from 'react';
import { loadStripe, type Stripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { Loader2, CreditCard, CheckCircle2 } from 'lucide-react';

let stripePromise: Promise<Stripe | null> | null = null;

function getStripe() {
  if (!stripePromise) {
    stripePromise = fetch('/billing/config')
      .then((r) => r.json())
      .then((cfg: { publishable_key: string }) => loadStripe(cfg.publishable_key));
  }
  return stripePromise;
}

function CheckoutForm({
  onSuccess,
  onCancel,
}: {
  onSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setLoading(true);
    setError(null);

    const { error: submitError } = await elements.submit();
    if (submitError) {
      setError(submitError.message || 'Payment failed');
      setLoading(false);
      return;
    }

    const { error: confirmError, paymentIntent } = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    });

    if (confirmError) {
      setError(confirmError.message || 'Payment failed');
      setLoading(false);
      return;
    }

    if (paymentIntent) {
      onSuccess(paymentIntent.id);
    }
    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <PaymentElement />
      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={!stripe || loading}
          className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 text-white font-semibold transition-all flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <CreditCard className="w-4 h-4" />
              Pay & Submit
            </>
          )}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={loading}
          className="px-4 py-3 rounded-xl border border-white/10 text-slate-400 hover:text-white transition-all"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export function StripePaymentModal({
  clientSecret,
  onSuccess,
  onCancel,
}: {
  clientSecret: string;
  onSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
}) {
  const [stripeLoaded, setStripeLoaded] = useState<Stripe | null>(null);

  useEffect(() => {
    getStripe().then((s) => setStripeLoaded(s));
  }, []);

  if (!stripeLoaded) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <Elements
      stripe={stripeLoaded}
      options={{
        clientSecret,
        appearance: {
          theme: 'night',
          variables: {
            colorPrimary: '#8b5cf6',
            colorBackground: '#1e293b',
            colorText: '#f0f0f2',
            colorDanger: '#ef4444',
            borderRadius: '12px',
          },
        },
      }}
    >
      <CheckoutForm onSuccess={onSuccess} onCancel={onCancel} />
    </Elements>
  );
}

export function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, string> = {
    free: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    paygo: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    pro: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  };
  const labels: Record<string, string> = {
    free: 'Free',
    paygo: 'Pay-as-you-go',
    pro: 'Pro',
  };
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${styles[tier] || styles.free}`}
    >
      {labels[tier] || tier}
    </span>
  );
}
