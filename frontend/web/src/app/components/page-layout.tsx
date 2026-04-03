import { Link } from 'react-router';
import { motion } from 'motion/react';
import { Cpu, LogOut, User } from 'lucide-react';
import { ReactNode } from 'react';

interface PageLayoutProps {
  children: ReactNode;
  showAuth?: boolean;
}

export function PageLayout({ children, showAuth = true }: PageLayoutProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950 text-white">
      {/* Animated background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <motion.div 
          animate={{ 
            scale: [1, 1.2, 1],
            opacity: [0.15, 0.25, 0.15]
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-purple-600/20 rounded-full blur-3xl" 
        />
        <motion.div 
          animate={{ 
            scale: [1, 1.1, 1],
            opacity: [0.12, 0.2, 0.12]
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="absolute bottom-0 right-1/4 w-[800px] h-[800px] bg-blue-600/15 rounded-full blur-3xl" 
        />
        <motion.div 
          animate={{ 
            scale: [1, 1.3, 1],
            opacity: [0.08, 0.15, 0.08]
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          className="absolute top-1/2 left-1/2 w-[400px] h-[400px] bg-fuchsia-600/10 rounded-full blur-3xl" 
        />
      </div>

      {/* Grid overlay */}
      <div className="fixed inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS1vcGFjaXR5PSIwLjAzIiBzdHJva2Utd2lkdGg9IjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')] opacity-40 pointer-events-none" />

      <div className="relative z-10">
        {/* Navigation */}
        <motion.nav 
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="container mx-auto px-6 py-6 flex items-center justify-between"
        >
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shadow-lg shadow-purple-500/50">
              <Cpu className="w-6 h-6" />
            </div>
            <span className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              DCN
            </span>
          </Link>
          
          <div className="flex items-center gap-4">
            {showAuth ? (
              <>
                <Link to="/submit" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">
                  Submit Job
                </Link>
                <Link to="/my-jobs" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">
                  My Jobs
                </Link>
                <Link to="/dashboard" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">
                  Monitor
                </Link>
                <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10">
                  <User className="w-4 h-4 text-slate-400" />
                  <span className="text-sm text-slate-300">User</span>
                </div>
                <button className="p-2 rounded-lg hover:bg-white/10 transition-colors text-slate-400 hover:text-white">
                  <LogOut className="w-5 h-5" />
                </button>
              </>
            ) : (
              <>
                <Link to="/submit" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">
                  Submit
                </Link>
                <Link 
                  to="/login" 
                  className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 border border-white/10 transition-all text-sm font-medium"
                >
                  Sign In
                </Link>
              </>
            )}
          </div>
        </motion.nav>

        {/* Main content */}
        <main>{children}</main>

        {/* Footer */}
        <footer className="container mx-auto px-6 py-12 mt-20 border-t border-white/5">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                <Cpu className="w-5 h-5" />
              </div>
              <span className="text-sm text-slate-400">© 2026 DCN. Distributed Compute Network.</span>
            </div>
            <div className="flex items-center gap-6 text-sm text-slate-400">
              <Link to="/contact" className="hover:text-white transition-colors">Contact</Link>
              <Link to="/report-bug" className="hover:text-white transition-colors">Report Bug</Link>
              <span>Built with FastAPI, PostgreSQL, Gemini AI</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
