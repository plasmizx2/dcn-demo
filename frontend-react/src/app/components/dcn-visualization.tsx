import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { Cpu, Zap, CheckCircle2 } from 'lucide-react';

interface Task {
  id: number;
  workerId: number;
  progress: number;
  completed: boolean;
}

export function DCNVisualization() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [completedCount, setCompletedCount] = useState(0);

  const workerCount = 6;
  const workerPositions = Array.from({ length: workerCount }, (_, i) => {
    const angle = (i / workerCount) * Math.PI * 2 - Math.PI / 2;
    const radius = typeof window !== 'undefined' && window.innerWidth < 768 ? 120 : 200;
    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
      id: i
    };
  });

  useEffect(() => {
    // Auto-start processing every 6 seconds
    const interval = setInterval(() => {
      startProcessing();
    }, 6000);

    // Start immediately
    startProcessing();

    return () => clearInterval(interval);
  }, []);

  const startProcessing = () => {
    setIsProcessing(true);
    setCompletedCount(0);
    
    // Create 12 tasks
    const newTasks: Task[] = Array.from({ length: 12 }, (_, i) => ({
      id: i,
      workerId: i % workerCount,
      progress: 0,
      completed: false
    }));

    setTasks(newTasks);

    // Simulate task processing
    newTasks.forEach((task, index) => {
      setTimeout(() => {
        const duration = 1500 + Math.random() * 1000;
        const interval = setInterval(() => {
          setTasks(prev => {
            const updated = [...prev];
            const t = updated.find(t => t.id === task.id);
            if (t) {
              t.progress += 5;
              if (t.progress >= 100) {
                t.progress = 100;
                t.completed = true;
                clearInterval(interval);
                setCompletedCount(c => c + 1);
              }
            }
            return updated;
          });
        }, duration / 20);
      }, index * 200);
    });

    setTimeout(() => {
      setIsProcessing(false);
    }, 5000);
  };

  return (
    <div className="relative w-full h-[400px] md:h-[600px] flex items-center justify-center">
      {/* Center Node (Coordinator) */}
      <motion.div 
        className="absolute z-20"
        animate={isProcessing ? { scale: [1, 1.1, 1] } : {}}
        transition={{ duration: 2, repeat: isProcessing ? Infinity : 0 }}
      >
        <div className="relative">
          {/* Pulse rings */}
          {isProcessing && (
            <>
              <motion.div
                className="absolute inset-0 -m-4 rounded-full border-2 border-purple-500"
                animate={{ scale: [1, 2, 2], opacity: [0.5, 0, 0] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
              <motion.div
                className="absolute inset-0 -m-4 rounded-full border-2 border-blue-500"
                animate={{ scale: [1, 2, 2], opacity: [0.5, 0, 0] }}
                transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
              />
            </>
          )}
          
          {/* Main coordinator node */}
          <div className="w-14 h-14 md:w-20 md:h-20 rounded-xl md:rounded-2xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shadow-2xl shadow-purple-500/50 border-2 md:border-4 border-white/20">
            <Cpu className="w-7 h-7 md:w-10 md:h-10 text-white" />
          </div>
          
          {/* Label */}
          <div className="absolute -bottom-6 md:-bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
            <div className="text-[10px] md:text-xs font-bold text-white">Coordinator</div>
            <div className="text-[10px] md:text-xs text-purple-400">{completedCount}/12 complete</div>
          </div>
        </div>
      </motion.div>

      {/* Worker Nodes */}
      {workerPositions.map((pos) => {
        const workerTasks = tasks.filter(t => t.workerId === pos.id);
        const isActive = workerTasks.some(t => !t.completed && t.progress > 0);
        const hasCompleted = workerTasks.some(t => t.completed);

        return (
          <motion.div
            key={pos.id}
            className="absolute"
            style={{
              left: '50%',
              top: '50%',
              x: pos.x,
              y: pos.y,
            }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: pos.id * 0.1 }}
          >
            {/* Connection line to center */}
            <svg 
              className="absolute top-1/2 left-1/2 pointer-events-none"
              style={{
                width: Math.abs(pos.x) * 2 + 100,
                height: Math.abs(pos.y) * 2 + 100,
                left: pos.x > 0 ? -Math.abs(pos.x) - 50 : 'auto',
                right: pos.x <= 0 ? Math.abs(pos.x) - 50 : 'auto',
                top: -Math.abs(pos.y) - 50,
              }}
            >
              <motion.line
                x1={pos.x > 0 ? Math.abs(pos.x) + 50 : Math.abs(pos.x) * 2 + 50}
                y1={Math.abs(pos.y) + 50}
                x2={pos.x > 0 ? 0 : Math.abs(pos.x) * 2 + 100}
                y2={Math.abs(pos.y) + 50}
                stroke="url(#gradient)"
                strokeWidth="2"
                strokeDasharray="5,5"
                animate={isActive ? { strokeDashoffset: [0, -10] } : {}}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                opacity={isActive ? 0.6 : 0.2}
              />
              <defs>
                <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#a855f7" />
                  <stop offset="100%" stopColor="#3b82f6" />
                </linearGradient>
              </defs>
            </svg>

            {/* Worker node */}
            <motion.div
              animate={isActive ? { scale: [1, 1.15, 1] } : {}}
              transition={{ duration: 1, repeat: isActive ? Infinity : 0 }}
            >
              <div className={`w-16 h-16 rounded-xl flex items-center justify-center shadow-xl border-2 transition-all duration-300 ${
                isActive 
                  ? 'bg-gradient-to-br from-green-500 to-emerald-500 border-green-400/50 shadow-green-500/50' 
                  : hasCompleted
                  ? 'bg-gradient-to-br from-blue-600 to-blue-700 border-blue-400/30 shadow-blue-500/30'
                  : 'bg-slate-800/80 border-white/10'
              }`}>
                {isActive ? (
                  <Zap className="w-7 h-7 text-white animate-pulse" />
                ) : hasCompleted ? (
                  <CheckCircle2 className="w-7 h-7 text-white" />
                ) : (
                  <Cpu className="w-7 h-7 text-slate-400" />
                )}
              </div>
            </motion.div>

            {/* Worker label */}
            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs text-slate-400">
              Worker {pos.id + 1}
            </div>

            {/* Task particles flowing */}
            {workerTasks.map((task) => (
              !task.completed && task.progress > 0 && (
                <motion.div
                  key={task.id}
                  className="absolute top-1/2 left-1/2 w-2 h-2 rounded-full bg-gradient-to-r from-purple-400 to-blue-400"
                  initial={{ x: -pos.x, y: -pos.y, opacity: 0, scale: 0 }}
                  animate={{ x: 0, y: 0, opacity: 1, scale: 1 }}
                  transition={{ duration: 0.8 }}
                />
              )
            ))}

            {/* Completed task particles returning */}
            {workerTasks.map((task) => (
              task.completed && (
                <motion.div
                  key={`complete-${task.id}`}
                  className="absolute top-1/2 left-1/2 w-3 h-3 rounded-full bg-gradient-to-r from-green-400 to-emerald-400 shadow-lg shadow-green-500/50"
                  initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
                  animate={{ x: -pos.x, y: -pos.y, opacity: 0, scale: 0 }}
                  transition={{ duration: 0.8, delay: 0.2 }}
                />
              )
            ))}

            {/* Progress indicator */}
            {isActive && (
              <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 w-12 h-1 bg-slate-700 rounded-full overflow-hidden">
                <motion.div 
                  className="h-full bg-gradient-to-r from-green-400 to-emerald-400"
                  style={{ width: `${workerTasks[0]?.progress || 0}%` }}
                />
              </div>
            )}
          </motion.div>
        );
      })}

      {/* Floating task count indicators */}
      <div className="absolute top-2 md:top-4 left-1/2 -translate-x-1/2 px-3 md:px-6 py-2 md:py-3 rounded-full bg-slate-900/80 backdrop-blur-xl border border-purple-500/30 shadow-lg">
        <div className="flex flex-col md:flex-row items-center gap-1 md:gap-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
            <span className="text-xs md:text-sm font-medium text-white">12 Tasks</span>
          </div>
          <div className="hidden md:block w-px h-4 bg-white/20" />
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs md:text-sm font-medium text-white">{completedCount} Done</span>
          </div>
        </div>
      </div>

      {/* Info text */}
      <div className="absolute bottom-2 md:bottom-4 left-1/2 -translate-x-1/2 text-center px-4">
        <p className="text-xs md:text-sm text-slate-400">
          <span className="hidden md:inline">Watch tasks automatically distribute across {workerCount} worker nodes in parallel</span>
          <span className="md:hidden">Tasks distributed across {workerCount} workers</span>
        </p>
      </div>
    </div>
  );
}