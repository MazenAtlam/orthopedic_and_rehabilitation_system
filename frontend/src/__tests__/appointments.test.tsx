import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosResponse } from 'axios';
import { appointmentsApi, usersApi } from '../api/endpoints';
import { AppointmentsPage } from '../features/appointments/AppointmentsPage';
import { useAuthStore } from '../store/authStore';

jest.mock('../api/endpoints', () => ({
  appointmentsApi: {
    list: jest.fn(),
    book: jest.fn(),
    update: jest.fn(),
    cancel: jest.fn(),
    getAvailability: jest.fn(),
  },
  usersApi: {
    listStaff: jest.fn(),
    listPatients: jest.fn(),
  },
}));

const mockedAppointments = appointmentsApi as jest.Mocked<typeof appointmentsApi>;
const mockedUsers = usersApi as jest.Mocked<typeof usersApi>;

function ok<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as AxiosResponse['config'],
  };
}

function renderWithQuery() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AppointmentsPage />
    </QueryClientProvider>,
  );
}

describe('AppointmentsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.getState().login(
      {
        user_id: 3,
        email: 'patient@demo.ortho.local',
        role: 'patient',
        is_active: true,
        full_name: 'Omar Hassan',
        patient_id: 10,
      },
      'token',
    );
  });

  it('loads appointments from API and allows a patient to book an available slot and cancel', async () => {
    mockedAppointments.list.mockResolvedValue(
      ok([
        {
          appointment_id: 55,
          patient_id: 10,
          patient_name: 'Omar Hassan',
          staff_id: 2,
          staff_name: 'Dr. Karim Nabil',
          type: 'consultation',
          start_time: '2026-11-27T10:00:00Z',
          end_time: '2026-11-27T10:30:00Z',
          status: 'booked',
          notes: 'Knee checkup',
        },
      ]),
    );
    mockedUsers.listStaff.mockResolvedValue(
      ok([
        {
          staff_id: 2,
          user_id: 2,
          full_name: 'Dr. Karim Nabil',
          staff_type: 'doctor',
          specialty: 'Orthopedics',
          license_no: 'LIC-1',
          phone: null,
        },
      ]),
    );
    mockedAppointments.getAvailability.mockResolvedValue(ok(['2026-11-27T11:00:00Z']));
    mockedAppointments.book.mockResolvedValueOnce(
      ok({
        appointment_id: 56,
        patient_id: 10,
        staff_id: 2,
        type: 'consultation',
        start_time: '2026-11-27T11:00:00Z',
        end_time: '2026-11-27T11:30:00Z',
        status: 'booked',
      }),
    );
    mockedAppointments.cancel.mockResolvedValueOnce(
      ok({
        appointment_id: 55,
        patient_id: 10,
        staff_id: 2,
        type: 'consultation',
        start_time: '2026-11-27T10:00:00Z',
        end_time: '2026-11-27T10:30:00Z',
        status: 'cancelled',
      }),
    );

    renderWithQuery();

    expect(await screen.findByText('Omar Hassan')).toBeInTheDocument();
    // Patients cannot mark completed, only cancel
    expect(screen.queryByLabelText('Complete appointment 55')).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('Cancel appointment 55'));
    expect(mockedAppointments.cancel).toHaveBeenCalledWith(55);

    await userEvent.click(screen.getByRole('button', { name: /New Appointment/i }));
    await waitFor(() => {
      expect(screen.getByText('11:00 UTC')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole('button', { name: /Confirm Booking/i }));

    await waitFor(() => {
      expect(mockedAppointments.book).toHaveBeenCalledWith(
        expect.objectContaining({
          patient_id: 10,
          staff_id: 2,
          start_time: '2026-11-27T11:00:00Z',
        }),
      );
    });
  });
});
