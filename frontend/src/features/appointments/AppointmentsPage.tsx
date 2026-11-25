import React, { useState } from 'react';
import { Plus, Clock, CheckCircle2, XCircle } from 'lucide-react';
import type { Appointment } from '../../types';
import { formatDateTime } from '../../utils/formatters';
import { usePermissions } from '../../hooks/usePermissions';

const INITIAL_APPOINTMENTS: Appointment[] = [
  {
    appointment_id: 101,
    patient_id: 101,
    patient_name: 'Omar Hassan',
    staff_id: 10,
    staff_name: 'Dr. Karim Nabil',
    type: 'imaging',
    start_time: '2026-11-25T10:30:00Z',
    end_time: '2026-11-25T11:00:00Z',
    status: 'booked',
    notes: 'Knee MRI Follow-up',
  },
  {
    appointment_id: 102,
    patient_id: 102,
    patient_name: 'Mariam Adel',
    staff_id: 11,
    staff_name: 'Dr. Hoda Youssef',
    type: 'therapy',
    start_time: '2026-11-25T12:00:00Z',
    end_time: '2026-11-25T12:45:00Z',
    status: 'booked',
    notes: 'Post-op Shoulder Rehabilitation Session',
  },
];

export const AppointmentsPage: React.FC = () => {
  const [appointments, setAppointments] = useState<Appointment[]>(INITIAL_APPOINTMENTS);
  const [showModal, setShowModal] = useState(false);
  const [patientName, setPatientName] = useState('');
  const [aptType, setAptType] = useState<Appointment['type']>('consultation');
  const [startTime, setStartTime] = useState('');
  const [notes, setNotes] = useState('');
  const { isPatient } = usePermissions();

  const handleBook = (e: React.FormEvent) => {
    e.preventDefault();
    const startIso = new Date(startTime).toISOString();
    const endIso = new Date(new Date(startTime).getTime() + 30 * 60000).toISOString();
    const newApt: Appointment = {
      appointment_id: Date.now(),
      patient_id: 101,
      patient_name: isPatient ? 'Omar Hassan' : patientName,
      staff_id: 10,
      staff_name: 'Dr. Karim Nabil',
      type: aptType,
      start_time: startIso,
      end_time: endIso,
      status: 'booked',
      notes,
    };
    setAppointments([newApt, ...appointments]);
    setShowModal(false);
    setPatientName('');
    setNotes('');
  };

  const updateStatus = (id: number, status: Appointment['status']) => {
    setAppointments((prev) =>
      prev.map((apt) => (apt.appointment_id === id ? { ...apt, status } : apt)),
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Appointment Management</h1>
          <p className="text-sm text-slate-500">
            Schedule consultations, physiotherapy sessions, and orthopedic imaging
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition"
        >
          <Plus className="w-4 h-4" />
          New Appointment
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
              <th className="py-3.5 px-4">Patient</th>
              <th className="py-3.5 px-4">Type & Clinician</th>
              <th className="py-3.5 px-4">Date & Time</th>
              <th className="py-3.5 px-4">Notes</th>
              <th className="py-3.5 px-4">Status</th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {appointments.map((apt) => (
              <tr key={apt.appointment_id} className="hover:bg-slate-50">
                <td className="py-3.5 px-4 font-medium text-slate-900">{apt.patient_name}</td>
                <td className="py-3.5 px-4">
                  <div className="text-slate-900 capitalize">{apt.type}</div>
                  <div className="text-xs text-slate-500">{apt.staff_name}</div>
                </td>
                <td className="py-3.5 px-4 text-slate-600">{formatDateTime(apt.start_time)}</td>
                <td className="py-3.5 px-4 text-slate-600">{apt.notes}</td>
                <td className="py-3.5 px-4">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium uppercase ${
                      apt.status === 'completed'
                        ? 'bg-emerald-50 text-emerald-700'
                        : apt.status === 'cancelled' || apt.status === 'no_show'
                          ? 'bg-rose-50 text-rose-700'
                          : 'bg-amber-50 text-amber-700'
                    }`}
                  >
                    <Clock className="w-3 h-3" />
                    {apt.status}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right space-x-2">
                  {apt.status === 'booked' && (
                    <>
                      <button
                        onClick={() => updateStatus(apt.appointment_id, 'completed')}
                        title="Mark Completed"
                        className="text-emerald-600 hover:bg-emerald-50 p-1.5 rounded-lg"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => updateStatus(apt.appointment_id, 'cancelled')}
                        title="Cancel"
                        className="text-rose-600 hover:bg-rose-50 p-1.5 rounded-lg"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Schedule Appointment</h2>
            <form onSubmit={handleBook} className="space-y-3.5">
              {!isPatient && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Patient Name
                  </label>
                  <input
                    required
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Appointment Type
                </label>
                <select
                  value={aptType}
                  onChange={(e) => setAptType(e.target.value as Appointment['type'])}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                >
                  <option value="consultation">Orthopedic Consultation</option>
                  <option value="therapy">Rehabilitation / Physiotherapy</option>
                  <option value="imaging">Radiology / Imaging</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Date & Time</label>
                <input
                  type="datetime-local"
                  required
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Clinical Notes
                </label>
                <input
                  required
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g., Right knee X-ray, ACL checkup"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Confirm Booking
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
