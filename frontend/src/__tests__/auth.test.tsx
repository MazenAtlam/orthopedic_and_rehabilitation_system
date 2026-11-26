import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { AxiosResponse } from 'axios';
import { authApi } from '../api/endpoints';
import { LoginPage } from '../features/auth/LoginPage';
import { ProtectedRoute } from '../features/auth/ProtectedRoute';
import { RegisterPage } from '../features/auth/RegisterPage';
import { useAuthStore } from '../store/authStore';
import type { User } from '../types';

jest.mock('../api/endpoints', () => ({
  authApi: {
    login: jest.fn(),
    register: jest.fn(),
    logout: jest.fn(),
  },
}));

const mockedAuthApi = authApi as jest.Mocked<typeof authApi>;

function axiosOk<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as AxiosResponse['config'],
  };
}

describe('Authentication & RBAC flows', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.getState().logout();
  });

  it('logs in via authApi.login and does not render quick-demo buttons', async () => {
    const staffUser: User = {
      user_id: 2,
      email: 'doctor@demo.ortho.local',
      role: 'staff',
      is_active: true,
      full_name: 'Dr. Karim Nabil',
      staff_type: 'doctor',
      staff_id: 1,
    };
    mockedAuthApi.login.mockResolvedValueOnce(
      axiosOk({
        access_token: 'real-jwt-token',
        token_type: 'Bearer',
        expires_in: 900,
        user: staffUser,
      }),
    );

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<div>Dashboard Home</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByText(/Quick Role Preview/i)).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/Email Address/i), 'doctor@demo.ortho.local');
    await userEvent.type(screen.getByLabelText(/Password/i), 'Test@12345');
    await userEvent.click(screen.getByRole('button', { name: /Sign In/i }));

    await waitFor(() => {
      expect(screen.getByText('Dashboard Home')).toBeInTheDocument();
    });
    expect(mockedAuthApi.login).toHaveBeenCalledWith('doctor@demo.ortho.local', 'Test@12345');
    expect(useAuthStore.getState().accessToken).toBe('real-jwt-token');
    expect(useAuthStore.getState().user?.email).toBe('doctor@demo.ortho.local');
  });

  it('displays structured error alert when login fails', async () => {
    mockedAuthApi.login.mockRejectedValueOnce(new Error('Invalid credentials'));

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText(/Email Address/i), 'wrong@demo.ortho.local');
    await userEvent.type(screen.getByLabelText(/Password/i), 'WrongPass123');
    await userEvent.click(screen.getByRole('button', { name: /Sign In/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
  });

  it('registers a patient with gender and signs in automatically', async () => {
    const newPatient: User = {
      user_id: 9,
      email: 'nadia@demo.ortho.local',
      role: 'patient',
      is_active: true,
      full_name: 'Nadiaadel',
      patient_id: 4,
    };
    mockedAuthApi.register.mockResolvedValueOnce(
      axiosOk({
        user_id: 9,
        patient_id: 4,
        email: 'nadia@demo.ortho.local',
        role: 'patient',
        user: newPatient,
      }),
    );
    mockedAuthApi.login.mockResolvedValueOnce(
      axiosOk({
        access_token: 'patient-jwt',
        token_type: 'Bearer',
        expires_in: 900,
        user: newPatient,
      }),
    );

    render(
      <MemoryRouter initialEntries={['/register']}>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/dashboard" element={<div>Patient Dashboard</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText(/Full Name/i), 'Nadia Adel');
    await userEvent.type(screen.getByLabelText(/Date of Birth/i), '1995-05-10');
    await userEvent.selectOptions(screen.getByLabelText(/Gender/i), 'female');
    await userEvent.type(screen.getByLabelText(/Email/i), 'nadia@demo.ortho.local');
    await userEvent.type(screen.getByLabelText(/Password/i), 'Test@12345');
    await userEvent.click(screen.getByRole('button', { name: /Create Account/i }));

    await waitFor(() => {
      expect(screen.getByText('Patient Dashboard')).toBeInTheDocument();
    });
    expect(mockedAuthApi.register).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: 'Nadia Adel',
        email: 'nadia@demo.ortho.local',
        gender: 'female',
        birth_date: '1995-05-10',
      }),
    );
  });

  it('redirects unauthenticated users to /login and unauthorized roles to /dashboard', () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={['/users']}>
        <Routes>
          <Route path="/login" element={<div>Login Gate</div>} />
          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/users" element={<div>Users Admin</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Login Gate')).toBeInTheDocument();
    unmount();

    useAuthStore.getState().login(
      {
        user_id: 3,
        email: 'patient@demo.ortho.local',
        role: 'patient',
        is_active: true,
        full_name: 'Omar Hassan',
        patient_id: 1,
      },
      'pat-token',
    );

    render(
      <MemoryRouter initialEntries={['/users']}>
        <Routes>
          <Route path="/dashboard" element={<div>Safe Dashboard</div>} />
          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/users" element={<div>Users Admin</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Safe Dashboard')).toBeInTheDocument();
  });
});
