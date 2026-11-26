import { apiClient } from './client';
import type {
  Appointment,
  CdssResult,
  FhirBundle,
  FinancialReport,
  Icd10Code,
  Invoice,
  MedicalRecord,
  Patient,
  PatientReport,
  PaymentRecord,
  Prescription,
  RehabSession,
  Scan,
  ScanAnnotation,
  ServiceItem,
  Staff,
  SystemReport,
  TreatmentPlan,
  User,
} from '../types';

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
  birth_date: string;
  gender: 'male' | 'female';
  phone?: string | null;
  address?: string | null;
}

export const authApi = {
  register: (payload: RegisterPayload) =>
    apiClient.post<{
      user_id: number;
      patient_id: number;
      email: string;
      role: string;
      user: User;
    }>('/auth/register', payload),
  login: (email: string, password: string) =>
    apiClient.post<{ access_token: string; token_type: string; expires_in: number; user: User }>(
      '/auth/login',
      { email, password },
    ),
  logout: () => apiClient.post<{ message: string }>('/auth/logout'),
};

export const usersApi = {
  listUsers: (params?: { role?: string; is_active?: boolean; q?: string }) =>
    apiClient.get<User[]>('/users', { params }),
  createUser: (data: {
    email: string;
    password: string;
    role: 'admin' | 'staff';
    full_name?: string;
    staff_type?: string;
    specialty?: string;
  }) => apiClient.post<User>('/users', data),
  updateUser: (
    id: number,
    data: {
      role?: 'admin' | 'staff' | 'patient';
      is_active?: boolean;
      full_name?: string;
      staff_type?: string;
      specialty?: string;
    },
  ) => apiClient.patch<User>(`/users/${id}`, data),
  listPatients: (q?: string) =>
    apiClient.get<Patient[]>('/patients', { params: q ? { q } : undefined }),
  getPatient: (id: number) => apiClient.get<Patient>(`/patients/${id}`),
  updatePatient: (id: number, data: Partial<Patient>) =>
    apiClient.put<Patient>(`/patients/${id}`, data),
  listStaff: (params?: { staff_type?: string; q?: string }) =>
    apiClient.get<Staff[]>('/staff', { params }),
};

export const appointmentsApi = {
  list: (params?: { patient?: number; staff?: number; date?: string; status?: string }) =>
    apiClient.get<Appointment[]>('/appointments', { params }),
  book: (data: {
    patient_id: number;
    staff_id: number;
    type: Appointment['type'];
    start_time: string;
    end_time: string;
    notes?: string;
  }) => apiClient.post<Appointment>('/appointments', data),
  update: (
    id: number,
    data: {
      start_time?: string;
      end_time?: string;
      status?: Appointment['status'];
      type?: Appointment['type'];
      notes?: string;
    },
  ) => apiClient.patch<Appointment>(`/appointments/${id}`, data),
  cancel: (id: number) => apiClient.delete<Appointment>(`/appointments/${id}`),
  getAvailability: (staffId: number, date: string) =>
    apiClient.get<string[]>(`/staff/${staffId}/availability`, { params: { date } }),
};

export const clinicalApi = {
  getPatientRecords: (patientId: number) =>
    apiClient.get<MedicalRecord[]>(`/patients/${patientId}/records`),
  createRecord: (data: {
    patient_id: number;
    appointment_id?: number | null;
    visit_date?: string;
    chief_complaint?: string | null;
    affected_area?: string | null;
    diagnosis?: string | null;
    icd10_code?: string | null;
    notes?: string | null;
  }) => apiClient.post<MedicalRecord>('/records', data),
  updateRecord: (id: number, data: Partial<MedicalRecord>) =>
    apiClient.put<MedicalRecord>(`/records/${id}`, data),
  addPrescription: (
    recordId: number,
    data: {
      medication: string;
      dose?: string | null;
      frequency?: string | null;
      duration?: string | null;
      instructions?: string | null;
    },
  ) => apiClient.post<Prescription>(`/records/${recordId}/prescriptions`, data),
  getPatientPrescriptions: (patientId: number) =>
    apiClient.get<Prescription[]>(`/patients/${patientId}/prescriptions`),
};

export const rehabApi = {
  listPlans: (params?: { patient_id?: number; status?: string }) =>
    apiClient.get<TreatmentPlan[]>('/treatment-plans', { params }),
  createPlan: (data: {
    patient_id: number;
    record_id?: number | null;
    title: string;
    goal?: string | null;
    start_date: string;
    end_date?: string | null;
  }) => apiClient.post<TreatmentPlan>('/treatment-plans', data),
  updatePlan: (
    id: number,
    data: {
      title?: string;
      goal?: string | null;
      end_date?: string | null;
      status?: TreatmentPlan['status'];
    },
  ) => apiClient.patch<TreatmentPlan>(`/treatment-plans/${id}`, data),
  logSession: (
    planId: number,
    data: {
      appointment_id?: number | null;
      session_date?: string;
      exercises?: string | null;
      pain_score?: number | null;
      range_of_motion?: number | null;
      notes?: string | null;
    },
  ) => apiClient.post<RehabSession>(`/treatment-plans/${planId}/sessions`, data),
  listSessions: (planId: number) =>
    apiClient.get<RehabSession[]>(`/treatment-plans/${planId}/sessions`),
};

export const billingApi = {
  listServices: (includeInactive = false) =>
    apiClient.get<ServiceItem[]>('/services', {
      params: includeInactive ? { include_inactive: 'true' } : undefined,
    }),
  saveService: (data: {
    service_id?: number;
    name: string;
    description?: string | null;
    price: string | number;
    is_active?: boolean;
  }) => apiClient.post<ServiceItem>('/services', data),
  createInvoice: (data: {
    patient_id: number;
    appointment_id?: number;
    icd10_code?: string;
    issue_date?: string;
    due_date: string;
    items: { service_id: number; quantity: number }[];
  }) => apiClient.post<Invoice>('/invoices', data),
  listInvoices: (params?: { patient_id?: number; status?: string }) =>
    apiClient.get<Invoice[]>('/invoices', { params }),
  getInvoice: (id: number) => apiClient.get<Invoice>(`/invoices/${id}`),
  payInvoice: (
    id: number,
    data: { amount: string | number; method: 'cash' | 'card' | 'online'; simulate?: string },
    idempotencyKey?: string,
  ) =>
    apiClient.post<{ payment: PaymentRecord; invoice: Invoice }>(
      `/invoices/${id}/payments`,
      data,
      idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined,
    ),
  searchIcd10: (q = '') => apiClient.get<Icd10Code[]>('/icd10', { params: q ? { q } : undefined }),
};

export const reportsApi = {
  getSystem: (params?: { start?: string; end?: string }) =>
    apiClient.get<SystemReport>('/reports/system', { params }),
  getPatients: (params?: { start?: string; end?: string }) =>
    apiClient.get<PatientReport>('/reports/patients', { params }),
  getFinancial: (params?: { start?: string; end?: string }) =>
    apiClient.get<FinancialReport>('/reports/financial', { params }),
};

export const imagingApi = {
  uploadScan: (formData: FormData) =>
    apiClient.post<Scan>('/scans', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  listScans: (patientId: number) =>
    apiClient.get<Scan[]>('/scans', { params: { patient_id: patientId } }),
  getViewerToken: (scanId: number) =>
    apiClient.get<{ viewer_token: string; ohif_url: string }>(`/scans/${scanId}/viewer-token`),
  analyzeScan: (scanId: number) => apiClient.post<CdssResult>(`/scans/${scanId}/analyze`),
  getCdssResult: (scanId: number) => apiClient.get<CdssResult>(`/scans/${scanId}/cdss-result`),
  reviewCdssResult: (resultId: number, review_status: 'accepted' | 'rejected') =>
    apiClient.patch<CdssResult>(`/cdss-results/${resultId}/review`, { review_status }),
  listAnnotations: (scanId: number) =>
    apiClient.get<ScanAnnotation[]>(`/scans/${scanId}/annotations`),
  saveAnnotation: (
    scanId: number,
    data: Omit<ScanAnnotation, 'annotation_id' | 'scan_id' | 'created_by' | 'created_at'>,
  ) => apiClient.post<ScanAnnotation>(`/scans/${scanId}/annotations`, data),
};

export const fhirApi = {
  getMetadata: () => apiClient.get<Record<string, unknown>>('/fhir/metadata'),
  searchResource: <T = Record<string, unknown>>(
    resourceType: string,
    params?: Record<string, string>,
  ) => apiClient.get<FhirBundle<T>>(`/fhir/${resourceType}`, { params }),
  readResource: <T = Record<string, unknown>>(resourceType: string, id: string | number) =>
    apiClient.get<T>(`/fhir/${resourceType}/${id}`),
  createResource: <T = Record<string, unknown>>(
    resourceType: string,
    body: Record<string, unknown>,
  ) => apiClient.post<T>(`/fhir/${resourceType}`, body),
};
