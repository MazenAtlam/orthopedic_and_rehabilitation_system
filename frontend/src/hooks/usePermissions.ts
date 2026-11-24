import { useAuthStore } from '../store/authStore';
import type { UserRole } from '../types';

export const usePermissions = () => {
  const user = useAuthStore((state) => state.user);
  const role = user?.role;

  return {
    user,
    role,
    isAdmin: role === 'admin',
    isStaff: role === 'staff',
    isPatient: role === 'patient',
    hasRole: (allowed: UserRole[]) => (role ? allowed.includes(role) : false),
  };
};