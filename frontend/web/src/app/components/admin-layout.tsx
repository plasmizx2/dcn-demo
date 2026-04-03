import { Link, useLocation } from 'react-router';
import { 
  LayoutDashboard, 
  FileText, 
  Monitor, 
  Users, 
  Plus, 
  Clipboard,
  LogOut,
  Cpu,
  Menu,
  X,
  Mail,
  Bug,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { ReactNode, useEffect, useState } from 'react';

interface AdminLayoutProps {
  children: ReactNode;
}

interface User {
  id: string;
  name?: string;
  email: string;
  role: string;
  avatar_url?: string;
}

export function AdminLayout({ children }: AdminLayoutProps) {
  const location = useLocation();
  const [user, setUser] = useState<User | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    fetch('/auth/me', { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(u => {
        if (u) setUser(u);
      })
      .catch(() => {});
  }, []);

  const navItems = [
    { path: '/submit', label: 'Submit Job', icon: Plus },
    { path: '/ops', label: 'Dashboard', icon: LayoutDashboard, adminOnly: true },
    { path: '/results', label: 'Results', icon: FileText, adminOnly: true },
    { path: '/worker-logs', label: 'Worker Logs', icon: Monitor, adminOnly: true },
    { path: '/admin/users', label: 'Users', icon: Users, adminOnly: true },
    { path: '/my-jobs', label: 'My Jobs', icon: Clipboard },
    { path: '/report-bug', label: 'Report Bug', icon: Bug },
    { path: '/contact', label: 'Contact', icon: Mail },
  ];

  const isAdmin = user?.role === 'admin' || user?.role === 'ceo';
  const filteredNavItems = navItems.filter(item => !item.adminOnly || isAdmin);

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950">
      {/* Animated background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <motion.div 
          animate={{ 
            scale: [1, 1.2, 1],
            opacity: [0.15, 0.25, 0.15]
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-1/4 -left-1/4 w-[800px] h-[800px] bg-purple-600/20 rounded-full blur-3xl" 
        />
        <motion.div 
          animate={{ 
            scale: [1, 1.1, 1],
            opacity: [0.12, 0.2, 0.12]
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="absolute bottom-1/4 -right-1/4 w-[800px] h-[800px] bg-blue-600/15 rounded-full blur-3xl" 
        />
      </div>

      {/* Grid overlay */}
      <div className="fixed inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS1vcGFjaXR5PSIwLjAzIiBzdHJva2Utd2lkdGg9IjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')] opacity-40 pointer-events-none" />

      {/* Mobile menu button */}
      <button
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-3 rounded-xl bg-slate-900/90 backdrop-blur-xl border border-white/10 text-white shadow-lg"
      >
        {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* Desktop Sidebar */}
      <motion.aside 
        initial={{ x: -100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="hidden lg:block fixed top-0 left-0 bottom-0 w-64 bg-slate-900/50 backdrop-blur-xl border-r border-white/5 z-40"
      >
        <div className="flex flex-col h-full p-4">
          {/* Logo */}
          <Link to="/" className="mb-8 mt-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
                <Cpu className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                  DCN
                </h1>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">
                  {isAdmin ? 'Admin Panel' : 'Customer'}
                </p>
              </div>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="flex-1 space-y-1">
            {filteredNavItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`
                    group relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200
                    ${isActive 
                      ? 'bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-white shadow-lg shadow-purple-500/10' 
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                    }
                  `}
                >
                  {isActive && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-gradient-to-r from-purple-500/20 to-blue-500/20 rounded-xl"
                      transition={{ type: 'spring', duration: 0.6 }}
                    />
                  )}
                  <Icon className={`w-4 h-4 relative z-10 ${isActive ? 'text-purple-400' : 'text-slate-500 group-hover:text-purple-400'}`} />
                  <span className="text-sm font-medium relative z-10">{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* User section */}
          <div className="pt-4 border-t border-white/5">
            {user ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3 px-3 py-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-sm font-bold text-white">
                    {user.name?.[0] || user.email[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{user.name || user.email}</p>
                    <p className="text-xs text-slate-500 capitalize">{user.role}</p>
                  </div>
                </div>
                <a
                  href="/auth/logout"
                  className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </a>
              </div>
            ) : (
              <Link
                to="/login"
                className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-white hover:bg-white/5 rounded-xl transition-colors"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </motion.aside>

      {/* Mobile Sidebar */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileMenuOpen(false)}
              className="lg:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            />
            
            {/* Sidebar */}
            <motion.aside
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="lg:hidden fixed top-0 left-0 bottom-0 w-72 bg-slate-900/95 backdrop-blur-xl border-r border-white/10 z-50"
            >
              <div className="flex flex-col h-full p-6">
                {/* Logo */}
                <Link to="/" className="mb-8 mt-2" onClick={() => setMobileMenuOpen(false)}>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
                      <Cpu className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                        DCN
                      </h1>
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">
                        {isAdmin ? 'Admin Panel' : 'Customer'}
                      </p>
                    </div>
                  </div>
                </Link>

                {/* Navigation */}
                <nav className="flex-1 space-y-1">
                  {filteredNavItems.map((item) => {
                    const isActive = location.pathname === item.path;
                    const Icon = item.icon;
                    
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`
                          group relative flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200
                          ${isActive 
                            ? 'bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-white shadow-lg shadow-purple-500/10' 
                            : 'text-slate-400 hover:text-white hover:bg-white/5'
                          }
                        `}
                      >
                        <Icon className={`w-5 h-5 ${isActive ? 'text-purple-400' : 'text-slate-500 group-hover:text-purple-400'}`} />
                        <span className="text-sm font-medium">{item.label}</span>
                      </Link>
                    );
                  })}
                </nav>

                {/* User section */}
                <div className="pt-4 border-t border-white/5">
                  {user ? (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3 px-3 py-2">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-sm font-bold text-white">
                          {user.name?.[0] || user.email[0]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white truncate">{user.name || user.email}</p>
                          <p className="text-xs text-slate-500 capitalize">{user.role}</p>
                        </div>
                      </div>
                      <a
                        href="/auth/logout"
                        className="flex items-center gap-2 px-3 py-3 text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-colors"
                      >
                        <LogOut className="w-5 h-5" />
                        Sign Out
                      </a>
                    </div>
                  ) : (
                    <Link
                      to="/login"
                      onClick={() => setMobileMenuOpen(false)}
                      className="flex items-center gap-2 px-3 py-3 text-sm text-slate-400 hover:text-white hover:bg-white/5 rounded-xl transition-colors"
                    >
                      Sign In
                    </Link>
                  )}
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 lg:ml-64 relative z-10">{children}</div>
    </div>
  );
}