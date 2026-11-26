export type UserRole = 'admin' | 'staff' | 'patient';
export type StaffType = 'doctor' | 'physiotherapist' | 'radiologist' | 'nurse';

export interface User {
  user_id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  full_name: string | null;
  staff_type?: StaffType | null;
  specialty?: string | null;
  patient_id?: number | null;
  staff_id?: number | null;
  created_at?: string;
}

export interface Patient {
  patient_id: number;
  user_id: number;
  email?: string;
  full_name: string;
  birth_date: string;
  gender: 'male' | 'female';
  phone: string | null;
  address: string | null;
  national_id?: string | null;
  emergency_contact: string | null;
}

export interface Staff {
  staff_id: number;
  user_id: number;
  email?: string;
  full_name: string;
  staff_type: StaffType;
  specialty: string | null;
  license_no: string | null;
  phone: string | null;
}

export interface Appointment {
  appointment_id: number;
  patient_id: number;
  patient_name?: string | null;
  staff_id: number;
  staff_name?: string | null;
  type: 'consultation' | 'therapy' | 'imaging';
  start_time: string;
  end_time: string;
  status: 'booked' | 'completed' | 'cancelled' | 'no_show';
  notes?: string | null;
}

export interface Icd10Code {
  code: string;
  description: string;
  category: string;
}

export interface MedicalRecord {
  record_id: number;
  patient_id: number;
  patient_name?: string | null;
  staff_id: number;
  staff_name?: string | null;
  appointment_id?: number | null;
  visit_date: string;
  chief_complaint: string | null;
  affected_area: string | null;
  diagnosis: string | null;
  icd10_code: string | null;
  icd10_description?: string | null;
  notes?: string | null;
}

export interface Prescription {
  prescription_id: number;
  record_id: number;
  patient_id?: number;
  medication: string;
  dose: string | null;
  frequency: string | null;
  duration: string | null;
  instructions: string | null;
  created_at?: string;
}

export interface TreatmentPlan {
  plan_id: number;
  patient_id: number;
  patient_name?: string | null;
  staff_id: number;
  staff_name?: string | null;
  record_id?: number | null;
  title: string;
  goal: string | null;
  start_date: string;
  end_date: string | null;
  status: 'active' | 'completed' | 'stopped';
}

export interface RehabSession {
  session_id: number;
  plan_id: number;
  appointment_id?: number | null;
  session_date: string;
  exercises: string | null;
  pain_score: number | null;
  range_of_motion: number | null;
  notes?: string | null;
}

export interface Scan {
  scan_id: number;
  patient_id: number;
  record_id?: number | null;
  study_uid: string;
  orthanc_id: string;
  modality: string | null;
  body_part: string | null;
  study_date: string | null;
  uploaded_by: number;
  uploaded_at: string;
}

export interface CdssResult {
  result_id: number;
  scan_id: number;
  model_version: string;
  finding: string | null;
  confidence: number | null;
  report_text: string | null;
  review_status: 'pending' | 'accepted' | 'rejected';
  reviewed_by?: number | null;
  created_at: string;
}

export interface ScanAnnotation {
  annotation_id: number;
  scan_id: number;
  created_by: number;
  type: 'arrow' | 'length' | 'angle' | 'note';
  data: Record<string, unknown>;
  note: string | null;
  created_at: string;
}

export interface ServiceItem {
  service_id: number;
  name: string;
  description?: string | null;
  price: number | string;
  is_active: boolean;
}

export interface InvoiceItem {
  item_id: number;
  invoice_id?: number;
  service_id: number;
  service_name?: string;
  quantity: number;
  unit_price: number | string;
  line_total?: number | string;
}

export interface PaymentRecord {
  payment_id: number;
  invoice_id?: number;
  amount: number | string;
  method: 'online' | 'cash' | 'card';
  status: 'pending' | 'success' | 'failed';
  paid_at?: string | null;
}

export interface Invoice {
  invoice_id: number;
  patient_id: number;
  patient_name?: string;
  appointment_id?: number | null;
  icd10_code?: string | null;
  issue_date: string;
  due_date: string;
  total_amount: number | string;
  amount_paid?: number | string;
  balance?: number | string;
  status: 'unpaid' | 'partial' | 'paid' | 'cancelled';
  items?: InvoiceItem[];
  payments?: PaymentRecord[];
}

export interface SystemReport {
  start: string;
  end: string;
  totals: {
    appointments: number;
    logins: number;
  };
  daily: {
    date: string;
    appointments: number;
    logins: number;
  }[];
  appointments_by_status: Record<'booked' | 'completed' | 'cancelled' | 'no_show', number>;
}

export interface PatientReport {
  start: string;
  end: string;
  totals: {
    patients: number;
    visits: number;
  };
  daily: {
    date: string;
    visits: number;
  }[];
  diagnoses: {
    code: string;
    description: string;
    visits: number;
  }[];
}

export interface FinancialReport {
  start: string;
  end: string;
  currency: string;
  totals: {
    revenue: number | string;
    outstanding: number | string;
    open_invoices: number;
  };
  daily: {
    date: string;
    revenue: number | string;
  }[];
}

export interface FhirBundleEntry<T = Record<string, unknown>> {
  fullUrl?: string;
  resource: T;
}

export interface FhirBundle<T = Record<string, unknown>> {
  resourceType: 'Bundle';
  type: string;
  total?: number;
  entry?: FhirBundleEntry<T>[];
}
