import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Activity, AlertCircle } from 'lucide-react';
import { queryClient } from '../../api/queryClient';
import { extractApiError } from '../../api/client';
import { authApi } from '../../api/endpoints';
import { useAuthStore } from '../../store/authStore';

export const RegisterPage: React.FC = () => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState<'male' | 'female'>('male');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const normalizedEmail = email.trim();
      await authApi.register({
        full_name: fullName.trim(),
        email: normalizedEmail,
        password,
        birth_date: dob,
        gender,
        phone: phone.trim() || null,
      });
      const loginResponse = await authApi.login(normalizedEmail, password);
      queryClient.clear();
      login(loginResponse.data.user, loginResponse.data.access_token);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(extractApiError(err, 'Registration failed. Please check your details.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2.5 bg-blue-600 rounded-xl text-white">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Patient Registration</h1>
            <p className="text-xs text-slate-500">Create your personal health portal account</p>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="mb-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label htmlFor="reg-fullname" className="block text-xs font-medium text-slate-700 mb-1">
              Full Name
            </label>
            <input
              id="reg-fullname"
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg border border-slate-300 text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="reg-dob" className="block text-xs font-medium text-slate-700 mb-1">
                Date of Birth
              </label>
              <input
                id="reg-dob"
                type="date"
                required
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className="w-full px-3.5 py-2 rounded-lg border border-slate-300 text-sm"
              />
            </div>
            <div>
              <label htmlFor="reg-gender" className="block text-xs font-medium text-slate-700 mb-1">
                Gender
              </label>
              <select
                id="reg-gender"
                value={gender}
                onChange={(e) => setGender(e.target.value as 'male' | 'female')}
                className="w-full px-3.5 py-2 rounded-lg border border-slate-300 text-sm bg-white"
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>
          <div>
            <label htmlFor="reg-phone" className="block text-xs font-medium text-slate-700 mb-1">
              Phone (Optional)
            </label>
            <input
              id="reg-phone"
              type="tel"
              placeholder="+20 100 123 4567"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label htmlFor="reg-email" className="block text-xs font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg border border-slate-300 text-sm"
            />
          </div>
          <div>
            <label htmlFor="reg-password" className="block text-xs font-medium text-slate-700 mb-1">
              Password
            </label>
            <input
              id="reg-password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg border border-slate-300 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg text-sm transition mt-2"
          >
            {isSubmitting ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-500">
          Already registered?{' '}
          <Link to="/login" className="text-blue-600 font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};
