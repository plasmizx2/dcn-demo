import { Link } from 'react-router';
import { motion } from 'motion/react';
import { 
  Zap, 
  Brain, 
  Network, 
  Shield, 
  Cpu, 
  TrendingUp,
  ArrowRight,
  CheckCircle2,
  Sparkles
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { DCNVisualization } from '../components/dcn-visualization';
import { useAuth } from '../hooks/use-auth';

export function LandingPage() {
  const { user, loading: authLoading } = useAuth();
  const [stats, setStats] = useState({
    jobs: 0,
    tasks: 0,
    completed: 0,
    workers: 0
  });

  useEffect(() => {
    // Fetch stats with animation
    fetch('/stats').then(r => r.json()).then(data => {
      setStats({
        jobs: data.total_jobs || 0,
        tasks: data.total_tasks || 0,
        completed: data.completed_jobs || 0,
        workers: data.worker_count || 0
      });
    }).catch(() => {});
  }, []);

  const features = [
    {
      icon: Brain,
      title: 'AI-Powered Planning',
      description: 'Intelligent task distribution powered by Gemini and Claude',
      color: 'from-purple-500 to-pink-500'
    },
    {
      icon: Network,
      title: 'Distributed Execution',
      description: 'Automatically parallelize workloads across multiple nodes',
      color: 'from-blue-500 to-cyan-500'
    },
    {
      icon: Zap,
      title: 'Instant Results',
      description: 'Real-time monitoring and aggregation of task outputs',
      color: 'from-yellow-500 to-orange-500'
    },
    {
      icon: Shield,
      title: 'Enterprise Ready',
      description: 'OAuth authentication, role-based access, and audit logs',
      color: 'from-green-500 to-emerald-500'
    }
  ];

  const steps = [
    { number: '01', title: 'Describe', desc: 'Explain your task in plain English' },
    { number: '02', title: 'Distribute', desc: 'System splits work across nodes' },
    { number: '03', title: 'Execute', desc: 'Workers process tasks in parallel' },
    { number: '04', title: 'Deliver', desc: 'Aggregated results ready instantly' }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950 text-white overflow-hidden">
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
          className="container mx-auto px-4 md:px-6 py-4 md:py-6 flex items-center justify-between"
        >
          <Link to="/" className="flex items-center gap-2 md:gap-3">
            <div className="w-8 h-8 md:w-10 md:h-10 rounded-lg md:rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shadow-lg shadow-purple-500/50">
              <Cpu className="w-5 h-5 md:w-6 md:h-6" />
            </div>
            <span className="text-xl md:text-2xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              DCN
            </span>
          </Link>
          
          <div className="flex items-center gap-2 md:gap-4">
            {!authLoading && user ? (
              <>
                <span className="hidden sm:inline text-xs md:text-sm text-slate-300 max-w-[160px] truncate">
                  {user.name || user.email}
                </span>
                <Link
                  to="/submit"
                  className="px-3 py-2 md:px-4 md:py-2 text-xs md:text-sm rounded-lg bg-white/10 hover:bg-white/20 border border-white/10 transition-all font-medium"
                >
                  Submit Job
                </Link>
                {(user.role === 'admin' || user.role === 'ceo') && (
                  <Link
                    to="/ops"
                    className="hidden md:inline px-3 py-2 text-sm rounded-lg bg-white/10 hover:bg-white/20 border border-white/10 transition-all font-medium"
                  >
                    Dashboard
                  </Link>
                )}
                <a
                  href="/auth/logout"
                  className="px-3 py-2 md:px-4 md:py-2 text-xs md:text-sm rounded-lg text-slate-300 hover:text-white border border-white/10 transition-all font-medium"
                >
                  Sign out
                </a>
              </>
            ) : !authLoading ? (
              <>
                <Link
                  to="/login"
                  className="px-3 py-2 md:px-4 md:py-2 text-xs md:text-sm rounded-lg bg-white/10 hover:bg-white/20 border border-white/10 transition-all font-medium"
                >
                  Sign In
                </Link>
                <Link
                  to="/submit"
                  className="px-3 py-2 md:px-6 md:py-3 text-xs md:text-base rounded-lg md:rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 font-semibold shadow-lg shadow-purple-500/50 transition-all"
                >
                  Get Started
                </Link>
              </>
            ) : (
              <div className="h-9 w-32 rounded-lg bg-white/5 animate-pulse" aria-hidden />
            )}
          </div>
        </motion.nav>

        {/* Hero Section */}
        <div className="container mx-auto px-4 md:px-6 pt-12 md:pt-20 pb-16 md:pb-32 text-center">
          <motion.div
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8 }}
          >
            <div className="inline-flex items-center gap-2 px-3 md:px-4 py-1.5 md:py-2 rounded-full bg-purple-500/20 border border-purple-500/30 mb-6 md:mb-8">
              <Sparkles className="w-3 h-3 md:w-4 md:h-4 text-purple-400" />
              <span className="text-xs md:text-sm font-medium text-purple-300">Powered by AI & Distributed Computing</span>
            </div>
            
            <h1 className="text-4xl sm:text-5xl md:text-7xl lg:text-8xl font-black mb-4 md:mb-6 leading-tight">
              <span className="block">Distributed Computing,</span>
              <span className="block mt-2 bg-gradient-to-r from-purple-400 via-fuchsia-400 to-blue-400 bg-clip-text text-transparent">
                Redefined
              </span>
            </h1>
            
            <p className="text-base md:text-xl lg:text-2xl text-slate-300 max-w-3xl mx-auto mb-8 md:mb-12 leading-relaxed px-4">
              Submit complex tasks in plain English. Watch as AI automatically splits, distributes, 
              and executes your workload across thousands of worker nodes in real-time.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 md:gap-4">
              <Link
                to="/submit"
                className="group w-full sm:w-auto px-6 md:px-8 py-3 md:py-4 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 text-white font-bold shadow-2xl shadow-purple-500/50 hover:shadow-purple-500/70 transition-all flex items-center justify-center gap-2 text-sm md:text-base"
              >
                Submit Your First Job
                <ArrowRight className="w-4 h-4 md:w-5 md:h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link
                to="/login"
                className="w-full sm:w-auto px-6 md:px-8 py-3 md:py-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 font-semibold backdrop-blur-xl transition-all text-sm md:text-base"
              >
                View Dashboard
              </Link>
            </div>
          </motion.div>

          {/* Stats */}
          <motion.div 
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.8 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-8 mt-16 md:mt-24 max-w-4xl mx-auto"
          >
            {[
              { label: 'Jobs Processed', value: stats.jobs.toLocaleString() },
              { label: 'Active Workers', value: stats.workers.toLocaleString() },
              { label: 'Tasks Complete', value: stats.tasks.toLocaleString() },
              { label: 'Success Rate', value: '99.9%' }
            ].map((stat, i) => (
              <motion.div
                key={i}
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.5 + i * 0.1 }}
                className="group relative p-4 md:p-6 rounded-2xl bg-slate-900/40 backdrop-blur-xl border border-white/5 hover:border-purple-500/30 transition-all cursor-pointer"
              >
                <div className="text-2xl md:text-4xl font-black bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent mb-1 md:mb-2">
                  {stat.value}
                </div>
                <div className="text-xs md:text-sm text-slate-400 font-medium">{stat.label}</div>
                <div className="absolute inset-0 bg-gradient-to-r from-purple-500/0 to-blue-500/0 group-hover:from-purple-500/5 group-hover:to-blue-500/5 rounded-2xl transition-all" />
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* Features */}
        <div className="container mx-auto px-6 py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-white">Powerful Capabilities</h2>
            <p className="text-slate-300 text-lg">Everything you need for distributed computing</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl mx-auto">
            {features.map((feature, i) => (
              <motion.div
                key={i}
                initial={{ y: 40, opacity: 0 }}
                whileInView={{ y: 0, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.5 }}
                whileHover={{ y: -8 }}
                className="group relative cursor-pointer"
              >
                {/* Card background with gradient border effect */}
                <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-600 to-blue-600 rounded-2xl blur opacity-0 group-hover:opacity-75 transition duration-500" />
                
                <div className="relative h-full p-8 rounded-2xl bg-slate-900/90 backdrop-blur-xl border border-white/10 overflow-hidden">
                  {/* Animated background pattern */}
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500">
                    <div className={`absolute inset-0 bg-gradient-to-br ${feature.color} opacity-5`} />
                    <div className="absolute inset-0" style={{
                      backgroundImage: `radial-gradient(circle at 2px 2px, rgba(255,255,255,0.05) 1px, transparent 0)`,
                      backgroundSize: '32px 32px'
                    }} />
                  </div>

                  {/* Floating gradient orb */}
                  <motion.div 
                    className={`absolute -top-10 -right-10 w-32 h-32 bg-gradient-to-br ${feature.color} rounded-full blur-2xl opacity-20 group-hover:opacity-40 transition-opacity duration-500`}
                    animate={{ 
                      scale: [1, 1.2, 1],
                      rotate: [0, 90, 0]
                    }}
                    transition={{ 
                      duration: 8, 
                      repeat: Infinity, 
                      ease: "easeInOut",
                      delay: i * 0.5
                    }}
                  />

                  <div className="relative">
                    {/* Icon with gradient background */}
                    <div className="mb-6">
                      <div className={`inline-flex p-4 rounded-xl bg-gradient-to-br ${feature.color} shadow-lg group-hover:shadow-2xl transition-shadow duration-300`}>
                        <feature.icon className="w-8 h-8 text-white" strokeWidth={2.5} />
                      </div>
                    </div>

                    <h3 className="text-2xl font-bold mb-3 text-white group-hover:bg-gradient-to-r group-hover:from-purple-300 group-hover:to-blue-300 group-hover:bg-clip-text group-hover:text-transparent transition-all duration-300">
                      {feature.title}
                    </h3>
                    <p className="text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors">
                      {feature.description}
                    </p>

                    {/* Decorative line */}
                    <div className="mt-6 h-1 w-0 group-hover:w-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500 rounded-full" />
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Live Demo Visualization */}
        <div className="container mx-auto px-6 py-20">
          <div className="text-center mb-12">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-500/20 border border-green-500/30 mb-6"
            >
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm font-medium text-green-300">Live Demo</span>
            </motion.div>
            <h2 className="text-4xl font-bold mb-4 text-white">See DCN In Action</h2>
            <p className="text-slate-300 text-lg max-w-2xl mx-auto">
              Watch how a single job automatically distributes across multiple worker nodes, processes in parallel, and aggregates results in real-time
            </p>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="max-w-6xl mx-auto p-8 rounded-3xl bg-slate-900/40 backdrop-blur-xl border border-purple-500/20 shadow-2xl"
          >
            <DCNVisualization />
          </motion.div>
        </div>

        {/* How it works */}
        <div className="container mx-auto px-6 py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-white">How It Works</h2>
            <p className="text-slate-300 text-lg">Four simple steps to distributed computing</p>
          </div>

          <div className="grid md:grid-cols-4 gap-6 max-w-7xl mx-auto">
            {steps.map((step, i) => (
              <motion.div
                key={i}
                initial={{ y: 40, opacity: 0 }}
                whileInView={{ y: 0, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.5 }}
                whileHover={{ y: -8, scale: 1.02 }}
                className="relative group"
              >
                <div className="relative p-6 rounded-2xl bg-slate-900/30 backdrop-blur-xl border border-white/10 hover:border-purple-500/50 transition-all overflow-hidden">
                  {/* Animated glow on hover */}
                  <div className="absolute inset-0 bg-gradient-to-br from-purple-500/0 to-blue-500/0 group-hover:from-purple-500/10 group-hover:to-blue-500/10 transition-all duration-500" />
                  
                  <div className="relative">
                    <motion.div 
                      className="text-7xl font-black mb-4 relative"
                      whileHover={{ scale: 1.1, rotate: 5 }}
                      transition={{ type: "spring", stiffness: 300 }}
                    >
                      <span className="absolute inset-0 bg-gradient-to-br from-purple-400 to-blue-400 bg-clip-text text-transparent blur-sm opacity-50">
                        {step.number}
                      </span>
                      <span className="relative bg-gradient-to-br from-purple-400 to-blue-400 bg-clip-text text-transparent">
                        {step.number}
                      </span>
                    </motion.div>
                    <h3 className="text-xl font-bold mb-2 text-white group-hover:text-purple-300 transition-colors">{step.title}</h3>
                    <p className="text-slate-300 text-sm leading-relaxed">{step.desc}</p>
                  </div>
                </div>
                {i < steps.length - 1 && (
                  <motion.div
                    animate={{ x: [0, 5, 0] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <ArrowRight className="hidden md:block absolute top-1/2 -right-3 -translate-y-1/2 w-6 h-6 text-purple-400/50" />
                  </motion.div>
                )}
              </motion.div>
            ))}
          </div>
        </div>

        {/* CTA Section */}
        <div className="container mx-auto px-6 py-20">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            whileInView={{ scale: 1, opacity: 1 }}
            viewport={{ once: true }}
            className="max-w-4xl mx-auto text-center p-12 rounded-3xl bg-gradient-to-r from-purple-500/20 to-blue-500/20 border border-purple-500/30"
          >
            <h2 className="text-4xl font-bold mb-4">Ready to get started?</h2>
            <p className="text-slate-300 text-lg mb-8">Join thousands of developers using DCN for distributed computing</p>
            <Link 
              to="/submit"
              className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 font-semibold shadow-lg shadow-purple-500/50 transition-all"
            >
              Start Your First Job
              <ArrowRight className="w-5 h-5" />
            </Link>
          </motion.div>
        </div>

        {/* Footer */}
        <footer className="container mx-auto px-6 py-12 border-t border-white/5">
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