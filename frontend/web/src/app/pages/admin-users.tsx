import { AdminLayout } from '../components/admin-layout';
import { motion } from 'motion/react';

export function AdminUsersPage() {
  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12">
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-4xl font-bold mb-3">Users & Access</h1>
          <p className="text-slate-400 text-lg mb-8">Manage user roles and permissions</p>

          <div className="bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 p-12 text-center">
            <p className="text-slate-400">User management - connect to backend API to manage users</p>
          </div>
        </motion.div>
      </div>
    </AdminLayout>
  );
}
