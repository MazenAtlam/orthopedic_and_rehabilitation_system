import React, { useState } from 'react';
import { Plus, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { Appointment } from '../../types';
import { formatDateTime } from '../../utils/formatters';
import { usePermissions } from '../../hooks/usePermissions';

const INITIAL_APPOINTMENTS: Appointment[] = [
  {
    id: 'apt-101',
    patientId: 'usr-pat-01',
    patientName: 'Omar Hassan',
    doctorId: 'usr-doc-01',
    doctorName: 'Dr. Karim Nabil',
    department: 'Radiology',
    scheduledAt: '2026-11-25T10:30:00Z',
    status: 'SCHEDULED',
    reason: 'Chest CT Scan Follow-up',
  },
  {
    id: 'apt-102',
    patientId: 'pat-202',
    patientName: 'Mariam Adel',
    doctorId: 'usr-doc-02',
    doctorName: 'Dr. Hoda Youssef',
    department: 'Cardiology',
    scheduledAt: '2026-11-25T12:00:00Z',
    status: 'CHECKED_IN',
    reason: 'Routine Echocardiogram',
  },
];

export const AppointmentsPage: React.FC = () => {
  const [appointments, setAppointments] = useState<Appointment[]>(INITIAL_APPOINTMENTS);
  const [showModal, setShowModal] = useState(false);
  const [patientName, setPatientName] = useState('');
  const [department, setDepartment] = useState('Radiology');
  const [scheduledAt, setScheduledAt] = useState('');
  const [reason, setReason] = useState('');
  const { isPatient } = usePermissions();

  const handleBook = (e: React.FormEvent) => {
    e.preventDefault();
    const newApt: Appointment = {
      id: `apt-${Date.now()}`,
      patientId: 'usr-pat-01',
      patientName: isPatient ? 'Omar Hassan' : patientName,
      doctorId: 'usr-doc-01',
      doctorName: 'Dr. Karim Nabil',
      department,
      scheduledAt: new Date(scheduledAt).toISOString(),
      status: 'SCHEDULED',
      reason,
    };
    setAppointments([newApt, ...appointments]);
    setShowModal(false);
    setPatientName('');
    setReason('');
  };

  const updateStatus = (id: string, status: Appointment['status']) => {
    setAppointments((prev) =>
      prev.map((apt) => (apt.id === id ? { ...apt, status } : apt))
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Appointment Management</h1>
          <p className="text-sm text-slate-500">Schedule and manage clinical consultations & scans</p>
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
              <th className="py-3.5 px-4">Department & Doctor</th>
              <th className="py-3.5 px-4">Date & Time</th>
              <th className="py-3.5 px-4">Reason</th>
              <th className="py-3.5 px-4">Status</th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {appointments.map((apt) => (
              <tr key={apt.id} className="hover:bg-slate-50">
                <td className="py-3.5 px-4 font-medium text-slate-900">{apt.patientName}</td>
                <td className="py-3.5 px-4">
                  <div className="text-slate-900">{apt.department}</div>
                  <div className="text-xs text-slate-500">{apt.doctorName}</div>
                </td>
                <td className="py-3.5 px-4 text-slate-600">{formatDateTime(apt.scheduledAt)}</td>
                <td className="py-3.5 px-4 text-slate-600">{apt.reason}</td>
                <td className="py-3.5 px-4">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      apt.status === 'COMPLETED'
                        ? 'bg-emerald-50 text-emerald-700'
                        : apt.status === 'CANCELLED'
                        ? 'bg-rose-50 text-rose-700'
                        : 'bg-amber-50 text-amber-700'
                    }`}
                  >
                    <Clock className="w-3 h-3" />
                    {apt.status}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right space-x-2">
                  {apt.status !== 'COMPLETED' && apt.status !== 'CANCELLED' && (
                    <>
                      <button
                        onClick={() => updateStatus(apt.id, 'COMPLETED')}
                        title="Mark Completed"
                        className="text-emerald-600 hover:bg-emerald-50 p-1.5 rounded-lg"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => updateStatus(apt.id, 'CANCELLED')}
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

      {/* Booking Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Schedule Appointment</h2>
            <form onSubmit={handleBook} className="space-y-3.5">
              {!isPatient && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Patient Name</label>
                  <input
                    required
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Department</label>
                <select
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                >
                  <option value="Radiology">Radiology</option>
                  <option value="Cardiology">Cardiology</option>
                  <option value="Neurology">Neurology</option>
                  <option value="General Medicine">General Medicine</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Date & Time</label>
                <input
                  type="datetime-local"
                  required
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Clinical Reason</label>
                <input
                  required
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g., Brain MRI, Follow-up"
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