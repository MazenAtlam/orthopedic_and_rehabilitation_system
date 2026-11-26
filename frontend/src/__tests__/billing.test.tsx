import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosResponse } from 'axios';
import { billingApi, usersApi } from '../api/endpoints';
import { BillingPage } from '../features/billing/BillingPage';
import { useAuthStore } from '../store/authStore';

jest.mock('../api/endpoints', () => ({
  billingApi: {
    listServices: jest.fn(),
    saveService: jest.fn(),
    createInvoice: jest.fn(),
    listInvoices: jest.fn(),
    payInvoice: jest.fn(),
    searchIcd10: jest.fn(),
  },
  usersApi: {
    listPatients: jest.fn(),
  },
}));

const mockedBilling = billingApi as jest.Mocked<typeof billingApi>;
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

describe('BillingPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedBilling.listServices.mockResolvedValue(
      ok([
        {
          service_id: 1,
          name: 'Consultation',
          description: 'Visit',
          price: '300.00',
          is_active: true,
        },
      ]),
    );
    mockedBilling.listInvoices.mockResolvedValue(
      ok([
        {
          invoice_id: 101,
          patient_id: 1,
          icd10_code: 'M25.5',
          issue_date: '2026-11-20',
          due_date: '2026-12-04',
          total_amount: '500.00',
          balance: '500.00',
          status: 'unpaid',
        },
      ]),
    );
    mockedUsers.listPatients.mockResolvedValue(
      ok([
        {
          patient_id: 1,
          user_id: 4,
          full_name: 'Omar Hassan',
          birth_date: '1990-01-01',
          gender: 'male',
          phone: null,
          address: null,
          emergency_contact: null,
        },
      ]),
    );
    mockedBilling.searchIcd10.mockResolvedValue(
      ok([{ code: 'M25.5', description: 'Pain in joint', category: 'Musculoskeletal' }]),
    );
  });

  it('displays EGP balance and lets a patient pay online via billingApi.payInvoice', async () => {
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
    mockedBilling.payInvoice.mockResolvedValueOnce(
      ok({
        payment: {
          payment_id: 9,
          amount: '500.00',
          method: 'online',
          status: 'success',
        },
        invoice: {
          invoice_id: 101,
          patient_id: 1,
          issue_date: '2026-11-20',
          due_date: '2026-12-04',
          total_amount: '500.00',
          balance: '0.00',
          status: 'paid',
        },
      }),
    );

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <BillingPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('INV-101')).toBeInTheDocument();
    expect(screen.getByText(/EGP\s*500\.00/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Pay Now/i }));
    await waitFor(() => {
      expect(mockedBilling.payInvoice).toHaveBeenCalledWith(101, {
        amount: '500.00',
        method: 'online',
      });
    });
  });

  it('hides Pay Now for clinical staff while allowing invoice generation', async () => {
    useAuthStore.getState().login(
      {
        user_id: 2,
        email: 'doctor@demo.ortho.local',
        role: 'staff',
        is_active: true,
        full_name: 'Dr. Karim Nabil',
        staff_id: 1,
      },
      'staff-token',
    );
    mockedBilling.createInvoice.mockResolvedValueOnce(
      ok({
        invoice_id: 102,
        patient_id: 1,
        issue_date: '2026-11-26',
        due_date: '2026-12-10',
        total_amount: '300.00',
        balance: '300.00',
        status: 'unpaid',
      }),
    );

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <BillingPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('INV-101')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Pay Now/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Generate Invoice/i }));
    await waitFor(() => {
      expect(mockedBilling.createInvoice).toHaveBeenCalledWith(
        expect.objectContaining({
          patient_id: 1,
          items: [{ service_id: 1, quantity: 1 }],
        }),
      );
    });
  });
});
