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
    // Clinical actions (write prescriptions, annotate/measure scans, save to EMR).
    // Phase 1 RBAC matrix: clinical staff only, admins and patients cannot.
    isClinical: role === 'staff',
    hasRole: (allowed: UserRole[]) => (role ? allowed.includes(role) : false),
  };
};
