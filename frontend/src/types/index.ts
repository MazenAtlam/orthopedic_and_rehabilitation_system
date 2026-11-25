export type UserRole = 'admin' | 'staff' | 'patient';
export type StaffType = 'doctor' | 'physiotherapist' | 'radiologist' | 'nurse';

export interface User {
  user_id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  full_name: string;
  staff_type?: StaffType;
  specialty?: string;
  patient_id?: number;
  staff_id?: number;
}

export interface Patient {
  patient_id: number;
  user_id: number;
  full_name: string;
  birth_date: string;
  gender: 'male' | 'female';
  phone: string;
  address: string;
  national_id: string;
  emergency_contact: string;
}

export interface Staff {
  staff_id: number;
  user_id: number;
  full_name: string;
  staff_type: StaffType;
  specialty: string;
  license_no: string;
  phone: string;
}

export interface Appointment {
  appointment_id: number;
  patient_id: number;
  patient_name?: string;
  staff_id: number;
  staff_name?: string;
  type: 'consultation' | 'therapy' | 'imaging';
  start_time: string;
  end_time: string;
  status: 'booked' | 'completed' | 'cancelled' | 'no_show';
  notes?: string;
}

export interface Icd10Code {
  code: string;
  description: string;
  category: string;
}

export interface MedicalRecord {
  record_id: number;
  patient_id: number;
  staff_id: number;
  staff_name?: string;
  visit_date: string;
  chief_complaint: string;
  affected_area: string;
  diagnosis: string;
  icd10_code: string;
  notes?: string;
}

export interface Prescription {
  prescription_id: number;
  record_id: number;
  medication: string;
  dose: string;
  frequency: string;
  duration: string;
  instructions: string;
}

export interface TreatmentPlan {
  plan_id: number;
  patient_id: number;
  staff_id: number;
  title: string;
  goal: string;
  start_date: string;
  end_date: string;
  status: 'active' | 'completed' | 'stopped';
}

export interface RehabSession {
  session_id: number;
  plan_id: number;
  appointment_id?: number;
  session_date: string;
  exercises: string;
  pain_score: number; // 0-10
  range_of_motion: number; // degrees
  notes?: string;
}

export interface Scan {
  scan_id: number;
  patient_id: number;
  record_id?: number;
  study_uid: string;
  orthanc_id: string;
  modality: string;
  body_part: string;
  study_date: string;
  uploaded_by: number;
  uploaded_at: string;
}

export interface CdssResult {
  result_id: number;
  scan_id: number;
  model_version: string;
  finding: string;
  confidence: number; // 0-1
  report_text: string;
  review_status: 'pending' | 'accepted' | 'rejected';
  reviewed_by?: number;
  created_at: string;
}

export interface ScanAnnotation {
  annotation_id: number;
  scan_id: number;
  created_by: number;
  type: 'arrow' | 'length' | 'angle' | 'note';
  data: Record<string, unknown>;
  note: string;
  created_at: string;
}

export interface ServiceItem {
  service_id: number;
  name: string;
  description: string;
  price: number;
  is_active: boolean;
}

export interface InvoiceItem {
  item_id: number;
  invoice_id: number;
  service_id: number;
  service_name?: string;
  quantity: number;
  unit_price: number;
}

export interface Invoice {
  invoice_id: number;
  patient_id: number;
  patient_name?: string;
  appointment_id?: number;
  icd10_code?: string;
  issue_date: string;
  due_date: string;
  total_amount: number;
  status: 'unpaid' | 'partial' | 'paid' | 'cancelled';
  items?: InvoiceItem[];
}
