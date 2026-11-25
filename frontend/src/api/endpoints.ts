import { apiClient } from './client';
import type {
  Appointment,
  CdssResult,
  Icd10Code,
  Invoice,
  MedicalRecord,
  Patient,
  Prescription,
  RehabSession,
  Scan,
  ScanAnnotation,
  ServiceItem,
  Staff,
  TreatmentPlan,
  User,
} from '../types';

export const authApi = {
  register: (payload: Record<string, unknown>) => apiClient.post('/auth/register', payload),
  login: (email: string, password: string) =>
    apiClient.post<{ access_token: string; user: User }>('/auth/login', { email, password }),
  logout: () => apiClient.post('/auth/logout'),
};

export const usersApi = {
  listUsers: () => apiClient.get<User[]>('/users'),
  createUser: (data: Partial<User> & { password: string }) => apiClient.post<User>('/users', data),
  updateUser: (id: number, data: Partial<User>) => apiClient.patch<User>(`/users/${id}`, data),
  listPatients: (q?: string) => apiClient.get<Patient[]>('/patients', { params: { q } }),
  getPatient: (id: number) => apiClient.get<Patient>(`/patients/${id}`),
  updatePatient: (id: number, data: Partial<Patient>) =>
    apiClient.put<Patient>(`/patients/${id}`, data),
  listStaff: () => apiClient.get<Staff[]>('/staff'),
};

export const appointmentsApi = {
  list: (params?: { patient?: number; staff?: number; date?: string; status?: string }) =>
    apiClient.get<Appointment[]>('/appointments', { params }),
  book: (data: Omit<Appointment, 'appointment_id' | 'status'>) =>
    apiClient.post<Appointment>('/appointments', data),
  update: (id: number, data: Partial<Appointment>) =>
    apiClient.patch<Appointment>(`/appointments/${id}`, data),
  cancel: (id: number) => apiClient.delete(`/appointments/${id}`),
  getAvailability: (staffId: number, date: string) =>
    apiClient.get<string[]>(`/staff/${staffId}/availability`, { params: { date } }),
};

export const clinicalApi = {
  getPatientRecords: (patientId: number) =>
    apiClient.get<MedicalRecord[]>(`/patients/${patientId}/records`),
  createRecord: (data: Omit<MedicalRecord, 'record_id'>) =>
    apiClient.post<MedicalRecord>('/records', data),
  updateRecord: (id: number, data: Partial<MedicalRecord>) =>
    apiClient.put<MedicalRecord>(`/records/${id}`, data),
  addPrescription: (recordId: number, data: Omit<Prescription, 'prescription_id' | 'record_id'>) =>
    apiClient.post<Prescription>(`/records/${recordId}/prescriptions`, data),
  getPatientPrescriptions: (patientId: number) =>
    apiClient.get<Prescription[]>(`/patients/${patientId}/prescriptions`),
};

export const rehabApi = {
  listPlans: (patientId?: number) =>
    apiClient.get<TreatmentPlan[]>('/treatment-plans', { params: { patient_id: patientId } }),
  createPlan: (data: Omit<TreatmentPlan, 'plan_id'>) =>
    apiClient.post<TreatmentPlan>('/treatment-plans', data),
  updatePlan: (id: number, data: Partial<TreatmentPlan>) =>
    apiClient.patch<TreatmentPlan>(`/treatment-plans/${id}`, data),
  logSession: (planId: number, data: Omit<RehabSession, 'session_id' | 'plan_id'>) =>
    apiClient.post<RehabSession>(`/treatment-plans/${planId}/sessions`, data),
  listSessions: (planId: number) =>
    apiClient.get<RehabSession[]>(`/treatment-plans/${planId}/sessions`),
};

export const billingApi = {
  listServices: () => apiClient.get<ServiceItem[]>('/services'),
  saveService: (data: Partial<ServiceItem>) => apiClient.post<ServiceItem>('/services', data),
  createInvoice: (data: {
    patient_id: number;
    appointment_id?: number;
    icd10_code?: string;
    due_date: string;
    items: { service_id: number; quantity: number }[];
  }) => apiClient.post<Invoice>('/invoices', data),
  listInvoices: () => apiClient.get<Invoice[]>('/invoices'),
  getInvoice: (id: number) => apiClient.get<Invoice>(`/invoices/${id}`),
  payInvoice: (id: number, data: { amount: number; method: 'cash' | 'card' | 'online' }) =>
    apiClient.post(`/invoices/${id}/payments`, data),
  searchIcd10: (q: string) => apiClient.get<Icd10Code[]>('/icd10', { params: { q } }),
};

export const reportsApi = {
  getSystem: () => apiClient.get('/reports/system'),
  getPatients: () => apiClient.get('/reports/patients'),
  getFinancial: () => apiClient.get('/reports/financial'),
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
  getMetadata: () => apiClient.get('/fhir/metadata'),
  searchResource: (resourceType: string, params?: Record<string, string>) =>
    apiClient.get(`/fhir/${resourceType}`, { params }),
  readResource: (resourceType: string, id: string | number) =>
    apiClient.get(`/fhir/${resourceType}/${id}`),
  createResource: (resourceType: string, body: Record<string, unknown>) =>
    apiClient.post(`/fhir/${resourceType}`, body),
};
