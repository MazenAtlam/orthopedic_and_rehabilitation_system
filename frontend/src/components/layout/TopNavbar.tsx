import React from 'react';
import { useAuthStore } from '../../store/authStore';
import type { UserRole } from '../../types';

export const TopNavbar: React.FC = () => {
  const { user, switchDemoRole } = useAuthStore();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold uppercase px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
          {user?.role}
        </span>
        {user?.specialty && <span className="text-xs text-slate-500">{user.specialty}</span>}
      </div>

      <div className="flex items-center gap-4">
        <select
          aria-label="Switch Role"
          value={user?.role}
          onChange={(e) => switchDemoRole(e.target.value as UserRole)}
          className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-slate-50 text-slate-700"
        >
          <option value="admin">View as Admin</option>
          <option value="staff">View as Clinical Staff</option>
          <option value="patient">View as Patient</option>
        </select>

        <div className="text-right">
          <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
          <p className="text-xs text-slate-500">{user?.email}</p>
        </div>
      </div>
    </header>
  );
};
