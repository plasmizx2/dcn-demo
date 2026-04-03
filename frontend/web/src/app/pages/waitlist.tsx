import { Link } from 'react-router';
import { motion } from 'motion/react';
import { Cpu, Clock, LogOut } from 'lucide-react';
import { useAuth } from '../hooks/use-auth';

export function WaitlistPage() {
  const { user } = useAuth();

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
        <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl p-8 text-center">
          {/* Logo */}
          <Link to="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shadow-lg shadow-purple-500/50">
              <Cpu className="w-7 h-7 text-white" />
            </div>
          </Link>

          {/* Status icon */}
          <div className="inline-flex p-4 rounded-full bg-amber-500/20 border border-amber-500/30 mb-6">
            <Clock className="w-8 h-8 text-amber-400" />
          </div>

          <h1 className="text-2xl font-bold text-white mb-3">You're on the Waitlist</h1>

          {user && (
            <p className="text-slate-400 text-sm mb-2">
              Signed in as <span className="text-white font-medium">{user.email}</span>
            </p>
          )}

          <p className="text-slate-300 text-sm leading-relaxed mb-8">
            Thanks for signing up! Your account is pending approval.
            We'll upgrade your access once a spot opens up — check back soon.
          </p>

          <div className="flex flex-col gap-3">
            <a
              href="/auth/logout"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 border border-white/10 text-sm font-medium transition-all"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </a>
            <Link
              to="/"
              className="text-sm text-slate-400 hover:text-white transition-colors"
            >
              Back to homepage
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
