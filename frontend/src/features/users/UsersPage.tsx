import React, { useState } from 'react';
import { UserPlus, Shield, CheckCircle2, Ban } from 'lucide-react';
import type { StaffType, User, UserRole } from '../../types';

const INITIAL_USERS: User[] = [
  {
    user_id: 1,
    full_name: 'Dr. Sarah Mansour',
    email: 'admin@orthorehab.clinic',
    role: 'admin',
    is_active: true,
  },
  {
    user_id: 2,
    full_name: 'Dr. Karim Nabil',
    email: 'k.nabil@orthorehab.clinic',
    role: 'staff',
    staff_type: 'doctor',
    specialty: 'Orthopedic Surgery',
    is_active: true,
  },
  {
    user_id: 3,
    full_name: 'Omar Hassan',
    email: 'omar.hassan@gmail.com',
    role: 'patient',
    is_active: true,
  },
];

export const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>(INITIAL_USERS);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('staff');
  const [staffType, setStaffType] = useState<StaffType>('doctor');
  const [specialty, setSpecialty] = useState('');

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    const newUser: User = {
      user_id: Date.now(),
      full_name: fullName,
      email,
      role,
      is_active: true,
      ...(role === 'staff' ? { staff_type: staffType, specialty } : {}),
    };
    setUsers([newUser, ...users]);
    setFullName('');
    setEmail('');
    setSpecialty('');
  };

  const toggleActiveStatus = (userId: number) => {
    setUsers((prev) =>
      prev.map((u) => (u.user_id === userId ? { ...u, is_active: !u.is_active } : u)),
    );
  };

  const handleRoleChange = (userId: number, newRole: UserRole) => {
    setUsers((prev) => prev.map((u) => (u.user_id === userId ? { ...u, role: newRole } : u)));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">User & Staff Account Management</h1>
        <p className="text-sm text-slate-500">
          Create staff or admin accounts, assign roles, and activate or deactivate users
        </p>
      </div>

      {/* Create Staff / Admin Form (POST /users) */}
      <form
        onSubmit={handleCreateUser}
        className="bg-white p-5 rounded-xl border border-slate-200 grid sm:grid-cols-5 gap-3 items-end"
      >
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Full Name</label>
          <input
            required
            placeholder="Dr. Ahmed Sami"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Email</label>
          <input
            type="email"
            required
            placeholder="a.sami@orthorehab.clinic"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">System Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
          >
            <option value="staff">Clinical Staff</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        {role === 'staff' ? (
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Staff Type</label>
            <select
              value={staffType}
              onChange={(e) => setStaffType(e.target.value as StaffType)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
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
          className="flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium"
        >
          <UserPlus className="w-4 h-4" />
          Add Account
        </button>
      </form>

      {/* Users Table (GET /users & PATCH /users/:id) */}
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
            {users.map((u) => (
              <tr key={u.user_id} className="hover:bg-slate-50">
                <td className="py-3.5 px-4">
                  <div className="font-medium text-slate-900">{u.full_name}</div>
                  <div className="text-xs text-slate-500">{u.email}</div>
                </td>
                <td className="py-3.5 px-4">
                  <select
                    value={u.role}
                    onChange={(e) => handleRoleChange(u.user_id, e.target.value as UserRole)}
                    className="text-xs font-medium border border-slate-200 rounded-lg px-2 py-1 bg-white"
                  >
                    <option value="admin">admin</option>
                    <option value="staff">staff</option>
                    <option value="patient">patient</option>
                  </select>
                </td>
                <td className="py-3.5 px-4 text-xs text-slate-600 capitalize">
                  {u.staff_type ? `${u.staff_type}${u.specialty ? ` • ${u.specialty}` : ''}` : '—'}
                </td>
                <td className="py-3.5 px-4">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      u.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                    }`}
                  >
                    <Shield className="w-3 h-3" />
                    {u.is_active ? 'Active' : 'Deactivated'}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right">
                  <button
                    onClick={() => toggleActiveStatus(u.user_id)}
                    className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
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
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
