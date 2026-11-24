import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, UserRole } from '../types';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  login: (user: User, accessToken: string) => void;
  setAccessToken: (token: string) => void;
  logout: () => void;
  switchDemoRole: (role: UserRole) => void;
}

const DEMO_USERS: Record<UserRole, User> = {
  admin: {
    user_id: 1,
    email: 'admin@orthorehab.clinic',
    role: 'admin',
    is_active: true,
    full_name: 'Dr. Sarah Mansour',
  },
  staff: {
    user_id: 2,
    email: 'k.nabil@orthorehab.clinic',
    role: 'staff',
    is_active: true,
    full_name: 'Dr. Karim Nabil',
    staff_type: 'doctor',
    specialty: 'Orthopedic Surgery & Sports Medicine',
    staff_id: 10,
  },
  patient: {
    user_id: 3,
    email: 'omar.hassan@gmail.com',
    role: 'patient',
    is_active: true,
    full_name: 'Omar Hassan',
    patient_id: 101,
  },
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      login: (user, accessToken) => set({ user, accessToken, isAuthenticated: true }),
      setAccessToken: (accessToken) => set({ accessToken }),
      logout: () => set({ user: null, accessToken: null, isAuthenticated: false }),
      switchDemoRole: (role) =>
        set({
          user: DEMO_USERS[role],
          accessToken: `mock-jwt-${role}`,
          isAuthenticated: true,
        }),
    }),
    { name: 'ortho-his-auth' }
  )
);