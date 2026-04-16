import { Link, useNavigate } from 'react-router';
import { motion } from 'motion/react';
import { Cpu, Github } from 'lucide-react';
import { useEffect } from 'react';
import { useAuth } from '../hooks/use-auth';

export function LoginPage() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (loading || !user) return;
    const dest = user.role === 'waitlister' ? '/waitlist' : (user.role === 'admin' || user.role === 'ceo') ? '/ops' : '/submit';
    navigate(dest, { replace: true });
  }, [loading, user, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950 flex items-center justify-center">
        <div className="h-10 w-10 rounded-full border-2 border-purple-500/30 border-t-purple-400 animate-spin" />
      </div>
    );
  }

  if (user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950 flex items-center justify-center p-6">
      {/* Animated background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <motion.div 
          animate={{ 
            scale: [1, 1.2, 1],
            opacity: [0.15, 0.25, 0.15]
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-1/3 left-1/3 w-[600px] h-[600px] bg-purple-600/20 rounded-full blur-3xl" 
        />
        <motion.div 
          animate={{ 
            scale: [1, 1.1, 1],
            opacity: [0.12, 0.2, 0.12]
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="absolute bottom-1/3 right-1/3 w-[600px] h-[600px] bg-blue-600/15 rounded-full blur-3xl" 
        />
      </div>

      <motion.div 
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl p-8">
          {/* Logo */}
          <div className="text-center mb-8">
            <Link to="/" className="inline-flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shadow-lg shadow-purple-500/50">
                <Cpu className="w-7 h-7 text-white" />
              </div>
            </Link>
            <h1 className="text-3xl font-bold mb-2">
              <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                DCN
              </span>
            </h1>
            <p className="text-slate-400 text-sm">Distributed Computation Network</p>
          </div>

          {/* OAuth Buttons */}
          <div className="space-y-4">
            {/* GitHub Primary Button */}
            <div className="space-y-2">
              <a
                href="/auth/github"
                className="group w-full flex items-center justify-center gap-3 px-6 py-4 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 transition-all border border-purple-500/50 hover:border-purple-400/50 text-white shadow-lg shadow-purple-500/20"
              >
                <Github className="w-5 h-5" />
                <span className="font-semibold">Continue with GitHub</span>
              </a>

              {/* GitHub Benefits */}
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-white/5 rounded-lg p-2 border border-white/10">
                  <div className="font-semibold text-purple-300 mb-1">🔐 Secure</div>
                  <div className="text-slate-400">Industry-standard OAuth</div>
                </div>
                <div className="bg-white/5 rounded-lg p-2 border border-white/10">
                  <div className="font-semibold text-blue-300 mb-1">✅ Works Everywhere</div>
                  <div className="text-slate-400">PR previews & all domains</div>
                </div>
                <div className="bg-white/5 rounded-lg p-2 border border-white/10">
                  <div className="font-semibold text-cyan-300 mb-1">⚡ Seamless</div>
                  <div className="text-slate-400">Already have a GitHub account</div>
                </div>
              </div>
            </div>

            {/* Divider */}
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-white/10" />
              <span className="text-xs text-slate-500 uppercase tracking-wider">or</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>

            {/* Google Alternative */}
            <a
              href="/auth/google"
              className="group w-full flex items-center justify-center gap-3 px-6 py-3.5 rounded-xl bg-white hover:bg-gray-50 transition-all border border-gray-200 hover:shadow-lg"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span className="font-semibold text-gray-700">Continue with Google</span>
            </a>
          </div>

          {/* Back link */}
          <div className="text-center">
            <Link 
              to="/" 
              className="text-sm text-slate-400 hover:text-white transition-colors inline-flex items-center gap-1"
            >
              ← Back to homepage
            </Link>
          </div>
        </div>

        {/* Trust indicators */}
        <div className="mt-6 text-center">
          <p className="text-xs text-slate-500">
            Trusted by thousands of developers worldwide
          </p>
        </div>
      </motion.div>
    </div>
  );
}