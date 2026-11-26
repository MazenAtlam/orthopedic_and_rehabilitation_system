import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AxiosResponse } from 'axios';
import { billingApi, clinicalApi, fhirApi, rehabApi, usersApi } from '../api/endpoints';
import { ClinicalEmrPage } from '../features/clinical/ClinicalEmrPage';
import { RehabPlansPage } from '../features/clinical/RehabPlansPage';
import { useAuthStore } from '../store/authStore';

jest.mock('../api/endpoints', () => ({
  usersApi: {
    listPatients: jest.fn(),
    getPatient: jest.fn(),
  },
  clinicalApi: {
    getPatientRecords: jest.fn(),
    createRecord: jest.fn(),
    addPrescription: jest.fn(),
    getPatientPrescriptions: jest.fn(),
  },
  billingApi: {
    searchIcd10: jest.fn(),
  },
  fhirApi: {
    searchResource: jest.fn(),
  },
  rehabApi: {
    listPlans: jest.fn(),
    createPlan: jest.fn(),
    updatePlan: jest.fn(),
    listSessions: jest.fn(),
    logSession: jest.fn(),
  },
}));

const mockedUsers = usersApi as jest.Mocked<typeof usersApi>;
const mockedClinical = clinicalApi as jest.Mocked<typeof clinicalApi>;
const mockedBilling = billingApi as jest.Mocked<typeof billingApi>;
const mockedFhir = fhirApi as jest.Mocked<typeof fhirApi>;
const mockedRehab = rehabApi as jest.Mocked<typeof rehabApi>;

function ok<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as AxiosResponse['config'],
  };
}

describe('ClinicalEmrPage & RehabPlansPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.getState().login(
      {
        user_id: 2,
        email: 'doctor@demo.ortho.local',
        role: 'staff',
        is_active: true,
        full_name: 'Dr. Karim Nabil',
        staff_type: 'doctor',
        staff_id: 1,
      },
      'staff-token',
    );

    mockedUsers.listPatients.mockResolvedValue(
      ok([
        {
          patient_id: 1,
          user_id: 4,
          full_name: 'Omar Hassan',
          birth_date: '1992-04-12',
          gender: 'male',
          phone: null,
          address: null,
          emergency_contact: null,
        },
      ]),
    );
    mockedUsers.getPatient.mockResolvedValue(
      ok({
        patient_id: 1,
        user_id: 4,
        full_name: 'Omar Hassan',
        birth_date: '1992-04-12',
        gender: 'male',
        phone: null,
        address: null,
        emergency_contact: null,
      }),
    );
  });

  it('loads EMR records, creates a visit with ICD-10 code, and renders live FHIR bundle', async () => {
    mockedClinical.getPatientRecords.mockResolvedValue(
      ok([
        {
          record_id: 7,
          patient_id: 1,
          staff_id: 1,
          staff_name: 'Dr. Karim Nabil',
          visit_date: '2026-11-20',
          chief_complaint: 'Knee pain',
          affected_area: 'Right Knee',
          diagnosis: 'Osteoarthritis of knee',
          icd10_code: 'M17.9',
          icd10_description: 'Osteoarthritis of knee, unspecified',
          notes: 'Follow-up in 2 weeks',
        },
      ]),
    );
    mockedClinical.getPatientPrescriptions.mockResolvedValue(ok([]));
    mockedBilling.searchIcd10.mockResolvedValue(
      ok([{ code: 'M17.9', description: 'Osteoarthritis of knee, unspecified', category: 'MSK' }]),
    );
    mockedFhir.searchResource.mockResolvedValue(
      ok({
        resourceType: 'Bundle',
        type: 'searchset',
        total: 1,
        entry: [{ resource: { resourceType: 'Condition', id: '7' } }],
      }),
    );
    mockedClinical.createRecord.mockResolvedValueOnce(
      ok({
        record_id: 8,
        patient_id: 1,
        staff_id: 1,
        visit_date: '2026-11-26',
        chief_complaint: 'Joint stiffness',
        affected_area: 'Left Knee',
        diagnosis: 'Joint effusion',
        icd10_code: 'M17.9',
        notes: null,
      }),
    );

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <ClinicalEmrPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/Osteoarthritis of knee \(Right Knee\)/i)).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText(/Chief complaint/i), 'Joint stiffness');
    await userEvent.type(screen.getByPlaceholderText(/Clinical diagnosis/i), 'Joint effusion');
    await userEvent.click(screen.getByRole('button', { name: /Save Visit/i }));

    await waitFor(() => {
      expect(mockedClinical.createRecord).toHaveBeenCalledWith(
        expect.objectContaining({
          patient_id: 1,
          chief_complaint: 'Joint stiffness',
          diagnosis: 'Joint effusion',
        }),
      );
    });

    await userEvent.click(screen.getByRole('button', { name: /HL7 FHIR R4 Payload/i }));
    await waitFor(() => {
      expect(mockedFhir.searchResource).toHaveBeenCalledWith('Condition', {
        patient: 'Patient/1',
      });
    });
  });

  it('loads rehab plans and logs a therapy session via rehabApi.logSession', async () => {
    mockedRehab.listPlans.mockResolvedValue(
      ok([
        {
          plan_id: 3,
          patient_id: 1,
          staff_id: 1,
          title: 'Knee Recovery Plan',
          goal: 'Full flexion',
          start_date: '2026-11-01',
          end_date: '2026-12-01',
          status: 'active',
        },
      ]),
    );
    mockedRehab.listSessions.mockResolvedValue(ok([]));
    mockedRehab.logSession.mockResolvedValueOnce(
      ok({
        session_id: 12,
        plan_id: 3,
        session_date: '2026-11-26',
        exercises: 'Heel slides',
        pain_score: 3,
        range_of_motion: 110,
        notes: null,
      }),
    );

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <RehabPlansPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Knee Recovery Plan')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Exercises Performed/i), 'Heel slides');
    await userEvent.click(screen.getByRole('button', { name: /Log Session/i }));

    await waitFor(() => {
      expect(mockedRehab.logSession).toHaveBeenCalledWith(
        3,
        expect.objectContaining({
          exercises: 'Heel slides',
          pain_score: 3,
          range_of_motion: 110,
        }),
      );
    });
  });
});
