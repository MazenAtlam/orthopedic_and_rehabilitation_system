import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { UserPlus, Shield, CheckCircle2, Ban, AlertCircle, Search } from 'lucide-react';
import { extractApiError } from '../../api/client';
import { usersApi } from '../../api/endpoints';
import { useAuthStore } from '../../store/authStore';
import type { StaffType, User, UserRole } from '../../types';

export const UsersPage: React.FC = () => {
  const currentUser = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'admin' | 'staff'>('staff');
  const [staffType, setStaffType] = useState<StaffType>('doctor');
  const [specialty, setSpecialty] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ['users', roleFilter, search],
    queryFn: async () =>
      (
        await usersApi.listUsers({
          role: roleFilter || undefined,
          q: search.trim() || undefined,
        })
      ).data,
  });

  const createMutation = useMutation({
    mutationFn: (payload: Parameters<typeof usersApi.createUser>[0]) =>
      usersApi.createUser(payload),
    onSuccess: () => {
      setActionError(null);
      setFullName('');
      setEmail('');
      setPassword('');
      setSpecialty('');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to create user account.')),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof usersApi.updateUser>[1] }) =>
      usersApi.updateUser(id, data),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to update user account.')),
  });

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      email: email.trim(),
      password,
      role,
      full_name: fullName.trim() || undefined,
      ...(role === 'staff'
        ? { staff_type: staffType, specialty: specialty.trim() || undefined }
        : {}),
    });
  };

  const toggleActiveStatus = (target: User) => {
    updateMutation.mutate({
      id: target.user_id,
      data: { is_active: !target.is_active },
    });
  };

  const handleRoleChange = (target: User, newRole: UserRole) => {
    updateMutation.mutate({
      id: target.user_id,
      data: {
        role: newRole,
        ...(newRole === 'staff' && !target.staff_type
          ? { staff_type: 'doctor', full_name: target.full_name || target.email }
          : {}),
      },
    });
  };

  const users = usersQuery.data ?? [];
  const errorMessage = actionError || (usersQuery.error ? extractApiError(usersQuery.error) : null);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">User & Staff Account Management</h1>
          <p className="text-sm text-slate-500">
            Create staff or admin accounts, assign roles, and activate or deactivate users
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              aria-label="Search users"
              placeholder="Search email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-1.5 bg-white border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <select
            aria-label="Filter by role"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-sm"
          >
            <option value="">All Roles</option>
            <option value="admin">Admin</option>
            <option value="staff">Staff</option>
            <option value="patient">Patient</option>
          </select>
        </div>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <form
        onSubmit={handleCreateUser}
        className="bg-white p-5 rounded-xl border border-slate-200 grid sm:grid-cols-6 gap-3 items-end"
      >
        <div>
          <label htmlFor="user-fullname" className="block text-xs font-medium text-slate-700 mb-1">
            Full Name
          </label>
          <input
            id="user-fullname"
            required={role === 'staff'}
            placeholder="Dr. Ahmed Sami"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label htmlFor="user-email" className="block text-xs font-medium text-slate-700 mb-1">
            Email
          </label>
          <input
            id="user-email"
            type="email"
            required
            placeholder="a.sami@demo.ortho.local"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label htmlFor="user-password" className="block text-xs font-medium text-slate-700 mb-1">
            Initial Password
          </label>
          <input
            id="user-password"
            type="password"
            required
            minLength={8}
            placeholder="Min 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label htmlFor="user-role" className="block text-xs font-medium text-slate-700 mb-1">
            System Role
          </label>
          <select
            id="user-role"
            value={role}
            onChange={(e) => setRole(e.target.value as 'admin' | 'staff')}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
          >
            <option value="staff">Clinical Staff</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        {role === 'staff' ? (
          <div>
            <label
              htmlFor="user-staff-type"
              className="block text-xs font-medium text-slate-700 mb-1"
            >
              Staff Type
            </label>
            <select
              id="user-staff-type"
              value={staffType}
              onChange={(e) => setStaffType(e.target.value as StaffType)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
            >
              <option value="doctor">Doctor</option>
              <option value="physiotherapist">Physiotherapist</option>
              <option value="radiologist">Radiologist</option>
              <option value="nurse">Nurse</option>
            </select>
          </div>
        ) : (
          <div />
        )}
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2 px-4 rounded-lg text-sm font-medium"
        >
          <UserPlus className="w-4 h-4" />
          Add Account
        </button>
      </form>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
              <th className="py-3.5 px-4">User</th>
              <th className="py-3.5 px-4">Role</th>
              <th className="py-3.5 px-4">Clinical Details</th>
              <th className="py-3.5 px-4">Account Status</th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {usersQuery.isLoading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-500">
                  Loading user accounts...
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-500">
                  No matching user accounts found.
                </td>
              </tr>
            ) : (
              users.map((u) => {
                const isSelf = u.user_id === currentUser?.user_id;
                return (
                  <tr key={u.user_id} className="hover:bg-slate-50">
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-slate-900">{u.full_name || '—'}</div>
                      <div className="text-xs text-slate-500">{u.email}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <select
                        aria-label={`Role for ${u.email}`}
                        disabled={isSelf || updateMutation.isPending}
                        value={u.role}
                        onChange={(e) => handleRoleChange(u, e.target.value as UserRole)}
                        className="text-xs font-medium border border-slate-200 rounded-lg px-2 py-1 bg-white disabled:opacity-60"
                      >
                        <option value="admin">admin</option>
                        <option value="staff">staff</option>
                        <option value="patient">patient</option>
                      </select>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-600 capitalize">
                      {u.staff_type
                        ? `${u.staff_type}${u.specialty ? ` • ${u.specialty}` : ''}`
                        : '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          u.is_active
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-rose-50 text-rose-700'
                        }`}
                      >
                        <Shield className="w-3 h-3" />
                        {u.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        disabled={isSelf || updateMutation.isPending}
                        onClick={() => toggleActiveStatus(u)}
                        className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition disabled:opacity-40 ${
                          u.is_active
                            ? 'text-rose-600 hover:bg-rose-50'
                            : 'text-emerald-600 hover:bg-emerald-50'
                        }`}
                      >
                        {u.is_active ? (
                          <>
                            <Ban className="w-3.5 h-3.5" /> Deactivate
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5" /> Activate
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
