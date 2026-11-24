import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Activity, ShieldCheck, Stethoscope, User as UserIcon } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import type { UserRole } from '../../types';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login, switchDemoRole } = useAuthStore();
  const navigate = useNavigate();

  const handleStandardLogin = (e: React.FormEvent) => {
    e.preventDefault();
    login(
      {
        user_id: 2,
        full_name: 'Dr. Karim Nabil',
        email,
        role: 'staff',
        is_active: true,
        staff_type: 'doctor',
        specialty: 'Orthopedic Surgery',
        staff_id: 10,
      },
      'sample-jwt-token'
    );
    navigate('/dashboard');
  };

  const handleQuickDemo = (role: UserRole) => {
    switchDemoRole(role);
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2.5 bg-blue-600 rounded-xl text-white">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">OrthoRehab HIS</h1>
            <p className="text-xs text-slate-500">Orthopedic & Rehabilitation Information System</p>
          </div>
        </div>

        <form onSubmit={handleStandardLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="doctor@orthorehab.clinic"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg text-sm transition"
          >
            Sign In
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-slate-100">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 text-center">
            Quick Role Preview (Dev Mode)
          </p>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => handleQuickDemo('admin')}
              className="flex flex-col items-center gap-1 p-2.5 rounded-lg border border-slate-200 hover:border-blue-500 hover:bg-blue-50 text-xs font-medium text-slate-700 transition"
            >
              <ShieldCheck className="w-4 h-4 text-indigo-600" />
              Admin
            </button>
            <button
              type="button"
              onClick={() => handleQuickDemo('staff')}
              className="flex flex-col items-center gap-1 p-2.5 rounded-lg border border-slate-200 hover:border-blue-500 hover:bg-blue-50 text-xs font-medium text-slate-700 transition"
            >
              <Stethoscope className="w-4 h-4 text-teal-600" />
              Staff
            </button>
            <button
              type="button"
              onClick={() => handleQuickDemo('patient')}
              className="flex flex-col items-center gap-1 p-2.5 rounded-lg border border-slate-200 hover:border-blue-500 hover:bg-blue-50 text-xs font-medium text-slate-700 transition"
            >
              <UserIcon className="w-4 h-4 text-blue-600" />
              Patient
            </button>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-slate-500">
          New patient?{' '}
          <Link to="/register" className="text-blue-600 font-medium hover:underline">
            Register for Patient Portal
          </Link>
        </p>
      </div>
    </div>
  );
};