import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { AxiosResponse } from 'axios';
import { authApi, fhirApi } from '../api/endpoints';
import { AppShell } from '../components/layout/AppShell';
import { DicomViewerPage } from '../features/dicom-cdss/DicomViewerPage';
import { useAuthStore } from '../store/authStore';
import { useDicomToolStore } from '../store/dicomToolStore';

jest.mock('../api/endpoints', () => ({
  authApi: {
    logout: jest.fn(),
  },
  fhirApi: {
    searchResource: jest.fn(),
  },
}));

const mockedAuth = authApi as jest.Mocked<typeof authApi>;
const mockedFhir = fhirApi as jest.Mocked<typeof fhirApi>;

function ok<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as AxiosResponse['config'],
  };
}

describe('AppShell navigation & DicomViewerPage workstation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useDicomToolStore.getState().resetView();
  });

  it('filters sidebar links by role, hides role-switcher, and calls authApi.logout on Sign Out', async () => {
    useAuthStore.getState().login(
      {
        user_id: 4,
        email: 'patient1@hcis.test',
        role: 'patient',
        is_active: true,
        full_name: 'Omar Hassan',
        patient_id: 1,
      },
      'patient-jwt',
    );
    mockedAuth.logout.mockResolvedValueOnce(ok({ message: 'Logged out.' }));

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<div>Signed Out Screen</div>} />
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<div>Patient Overview</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('OrthoRehab')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Switch Role/i)).not.toBeInTheDocument();
    // Patient sees Appointments & Billing, but NOT Admin User Management
    expect(screen.getByText('Appointments')).toBeInTheDocument();
    expect(screen.getByText('Billing & ICD-10')).toBeInTheDocument();
    expect(screen.queryByText('User Management')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Sign Out/i }));
    await waitFor(() => {
      expect(mockedAuth.logout).toHaveBeenCalled();
      expect(screen.getByText('Signed Out Screen')).toBeInTheDocument();
    });
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('renders DicomViewerPage with FHIR ImagingStudy metadata and switches viewport layouts', async () => {
    useAuthStore.getState().login(
      {
        user_id: 2,
        email: 'doctor1@hcis.test',
        role: 'staff',
        is_active: true,
        full_name: 'Dr. Karim Nabil',
        staff_type: 'doctor',
        staff_id: 1,
      },
      'staff-jwt',
    );

    mockedFhir.searchResource.mockImplementation((resourceType: string) => {
      if (resourceType === 'ImagingStudy') {
        return Promise.resolve(
          ok({
            resourceType: 'Bundle',
            type: 'searchset',
            total: 1,
            entry: [
              {
                resource: {
                  resourceType: 'ImagingStudy',
                  id: '42',
                  subject: { reference: 'Patient/1' },
                  identifier: [{ system: 'urn:dicom:uid', value: 'urn:oid:2.25.999' }],
                },
              },
            ],
          }),
        );
      }
      return Promise.resolve(
        ok({
          resourceType: 'Bundle',
          type: 'searchset',
          total: 1,
          entry: [
            {
              resource: {
                resourceType: 'DiagnosticReport',
                id: '11',
                status: 'final',
                conclusion: 'Medial joint space narrowing consistent with OA.',
              },
            },
          ],
        }),
      );
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <DicomViewerPage />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText(/Medial joint space narrowing consistent with OA\./i),
    ).toBeInTheDocument();
    expect(screen.getByText('Study #42')).toBeInTheDocument();

    // Switch to MPR (3 planes: AXIAL, SAGITTAL, CORONAL) and 3D Vol
    await userEvent.click(screen.getByRole('button', { name: /MPR/i }));
    expect(screen.getByText(/SAGITTAL/)).toBeInTheDocument();
    expect(screen.getByText(/CORONAL/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /3D Vol/i }));
    expect(screen.getByText('3D Orthopedic Reconstruction')).toBeInTheDocument();
  });
});
