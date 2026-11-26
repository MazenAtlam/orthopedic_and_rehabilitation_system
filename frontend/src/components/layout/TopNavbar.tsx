import React from 'react';
import { useAuthStore } from '../../store/authStore';

export const TopNavbar: React.FC = () => {
  const user = useAuthStore((s) => s.user);

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold uppercase px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
          {user?.role}
        </span>
        {user?.staff_type && (
          <span className="text-xs capitalize text-slate-600 font-medium">{user.staff_type}</span>
        )}
        {user?.specialty && <span className="text-xs text-slate-500">• {user.specialty}</span>}
      </div>

      <div className="text-right">
        <p className="text-sm font-medium text-slate-900">{user?.full_name || user?.email}</p>
        <p className="text-xs text-slate-500">{user?.email}</p>
      </div>
    </header>
  );
};
