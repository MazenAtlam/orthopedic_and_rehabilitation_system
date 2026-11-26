import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Calendar,
  CreditCard,
  FileText,
  Scan,
  Dumbbell,
  Users,
  LogOut,
} from 'lucide-react';
import { queryClient } from '../../api/queryClient';
import { authApi } from '../../api/endpoints';
import { useAuthStore } from '../../store/authStore';
import type { UserRole } from '../../types';

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
  roles: UserRole[];
}

const NAV_ITEMS: NavItem[] = [
  {
    label: 'Dashboard & Reports',
    to: '/dashboard',
    icon: <BarChart3 className="w-4 h-4" />,
    roles: ['admin', 'staff', 'patient'],
  },
  {
    label: 'User Management',
    to: '/users',
    icon: <Users className="w-4 h-4" />,
    roles: ['admin'],
  },
  {
    label: 'Appointments',
    to: '/appointments',
    icon: <Calendar className="w-4 h-4" />,
    roles: ['admin', 'staff', 'patient'],
  },
  {
    label: 'Musculoskeletal EMR',
    to: '/clinical-emr',
    icon: <FileText className="w-4 h-4" />,
    roles: ['staff', 'patient'],
  },
  {
    label: 'Rehab & Physio Plans',
    to: '/rehab-plans',
    icon: <Dumbbell className="w-4 h-4" />,
    roles: ['staff', 'patient'],
  },
  {
    label: 'Orthanc DICOM & CDSS',
    to: '/dicom-viewer',
    icon: <Scan className="w-4 h-4" />,
    roles: ['staff', 'patient'],
  },
  {
    label: 'Billing & ICD-10',
    to: '/billing',
    icon: <CreditCard className="w-4 h-4" />,
    roles: ['admin', 'staff', 'patient'],
  },
];

export const Sidebar: React.FC = () => {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const visibleItems = NAV_ITEMS.filter((item) => (user ? item.roles.includes(user.role) : false));

  const handleSignOut = async () => {
    try {
      await authApi.logout();
    } catch {
      // Clear local session even if token has already expired
    } finally {
      queryClient.clear();
      logout();
      navigate('/login', { replace: true });
    }
  };

  return (
    <aside className="w-64 bg-slate-900 text-slate-200 flex flex-col min-h-screen shrink-0">
      <div className="h-16 px-6 flex items-center gap-3 border-b border-slate-800">
        <div className="p-1.5 bg-blue-600 rounded-lg text-white">
          <Activity className="w-5 h-5" />
        </div>
        <div>
          <span className="font-bold text-white tracking-tight block leading-none">OrthoRehab</span>
          <span className="text-[10px] text-slate-400">Team 03 • Clinical HIS</span>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <button
          type="button"
          onClick={handleSignOut}
          className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </aside>
  );
};
