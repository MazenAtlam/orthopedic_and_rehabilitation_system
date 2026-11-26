import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosResponse } from 'axios';
import { appointmentsApi, billingApi, rehabApi, reportsApi, usersApi } from '../api/endpoints';
import { AnalyticsPage } from '../features/analytics/AnalyticsPage';
import { UsersPage } from '../features/users/UsersPage';
import { useAuthStore } from '../store/authStore';

jest.mock('../api/endpoints', () => ({
  usersApi: {
    listUsers: jest.fn(),
    createUser: jest.fn(),
    updateUser: jest.fn(),
  },
  reportsApi: {
    getSystem: jest.fn(),
    getPatients: jest.fn(),
    getFinancial: jest.fn(),
  },
  appointmentsApi: {
    list: jest.fn(),
  },
  rehabApi: {
    listPlans: jest.fn(),
  },
  billingApi: {
    listInvoices: jest.fn(),
  },
}));

const mockedUsers = usersApi as jest.Mocked<typeof usersApi>;
const mockedReports = reportsApi as jest.Mocked<typeof reportsApi>;
const mockedAppointments = appointmentsApi as jest.Mocked<typeof appointmentsApi>;
const mockedRehab = rehabApi as jest.Mocked<typeof rehabApi>;
const mockedBilling = billingApi as jest.Mocked<typeof billingApi>;

function ok<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as AxiosResponse['config'],
  };
}

describe('UsersPage & AnalyticsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('creates a staff account on UsersPage and prevents admin self-deactivation', async () => {
    useAuthStore.getState().login(
      {
        user_id: 1,
        email: 'admin@demo.ortho.local',
        role: 'admin',
        is_active: true,
        full_name: 'Clinic Admin',
      },
      'admin-token',
    );

    mockedUsers.listUsers.mockResolvedValue(
      ok([
        {
          user_id: 1,
          email: 'admin@demo.ortho.local',
          role: 'admin',
          is_active: true,
          full_name: 'Clinic Admin',
        },
        {
          user_id: 2,
          email: 'doctor@demo.ortho.local',
          role: 'staff',
          is_active: true,
          full_name: 'Dr. Karim Nabil',
          staff_type: 'doctor',
        },
      ]),
    );
    mockedUsers.createUser.mockResolvedValueOnce(
      ok({
        user_id: 5,
        email: 'nurse@demo.ortho.local',
        role: 'staff',
        is_active: true,
        full_name: 'Nurse Sara',
        staff_type: 'nurse',
      }),
    );

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <UsersPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('doctor@demo.ortho.local')).toBeInTheDocument();
    const deactivateButtons = screen.getAllByRole('button', { name: /Deactivate/i });
    expect(deactivateButtons[0]).toBeDisabled(); // Admin self row
    expect(deactivateButtons[1]).toBeEnabled();

    await userEvent.type(screen.getByLabelText(/Full Name/i), 'Nurse Sara');
    await userEvent.type(screen.getByLabelText(/^Email$/i), 'nurse@demo.ortho.local');
    await userEvent.type(screen.getByLabelText(/Initial Password/i), 'Test@12345');
    await userEvent.click(screen.getByRole('button', { name: /Add Account/i }));

    await waitFor(() => {
      expect(mockedUsers.createUser).toHaveBeenCalledWith(
        expect.objectContaining({
          email: 'nurse@demo.ortho.local',
          role: 'staff',
          full_name: 'Nurse Sara',
        }),
      );
    });
  });

  it('queries admin reports for admin and avoids /reports/* for patient on AnalyticsPage', async () => {
    useAuthStore.getState().login(
      {
        user_id: 1,
        email: 'admin@demo.ortho.local',
        role: 'admin',
        is_active: true,
        full_name: 'Admin',
      },
      'admin-token',
    );

    mockedReports.getSystem.mockResolvedValue(
      ok({
        start: '2026-11-01',
        end: '2026-11-26',
        totals: { appointments: 12, logins: 5 },
        daily: [{ date: '2026-11-25', appointments: 4, logins: 2 }],
        appointments_by_status: { booked: 6, completed: 5, cancelled: 1, no_show: 0 },
      }),
    );
    mockedReports.getPatients.mockResolvedValue(
      ok({
        start: '2026-11-01',
        end: '2026-11-26',
        totals: { patients: 8, visits: 10 },
        daily: [{ date: '2026-11-25', visits: 3 }],
        diagnoses: [{ code: 'M25.5', description: 'Pain in joint', visits: 4 }],
      }),
    );
    mockedReports.getFinancial.mockResolvedValue(
      ok({
        start: '2026-11-01',
        end: '2026-11-26',
        currency: 'EGP',
        totals: { revenue: '1500.00', outstanding: '500.00', open_invoices: 1 },
        daily: [{ date: '2026-11-25', revenue: '1500.00' }],
      }),
    );

    const qc1 = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { unmount } = render(
      <QueryClientProvider client={qc1}>
        <AnalyticsPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/EGP\s*1,500\.00/)).toBeInTheDocument();
    expect(screen.getByText('M25.5')).toBeInTheDocument();
    unmount();

    jest.clearAllMocks();
    useAuthStore.getState().login(
      {
        user_id: 4,
        email: 'patient@demo.ortho.local',
        role: 'patient',
        is_active: true,
        full_name: 'Omar Hassan',
        patient_id: 1,
      },
      'patient-token',
    );
    mockedAppointments.list.mockResolvedValue(ok([]));
    mockedRehab.listPlans.mockResolvedValue(ok([]));
    mockedBilling.listInvoices.mockResolvedValue(ok([]));

    const qc2 = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc2}>
        <AnalyticsPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Upcoming Appointments')).toBeInTheDocument();
    expect(mockedReports.getSystem).not.toHaveBeenCalled();
    expect(mockedReports.getFinancial).not.toHaveBeenCalled();
  });
});
