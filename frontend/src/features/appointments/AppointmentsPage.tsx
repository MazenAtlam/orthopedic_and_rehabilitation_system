import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Clock, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { extractApiError } from '../../api/client';
import { appointmentsApi, usersApi } from '../../api/endpoints';
import { usePermissions } from '../../hooks/usePermissions';
import type { Appointment } from '../../types';
import { formatDateTime } from '../../utils/formatters';

function tomorrowIsoDate(): string {
  const date = new Date(Date.now() + 86400000);
  return date.toISOString().slice(0, 10);
}

export const AppointmentsPage: React.FC = () => {
  const { user, isPatient } = usePermissions();
  const queryClient = useQueryClient();

  const [showModal, setShowModal] = useState(false);
  const [selectedPatientId, setSelectedPatientId] = useState<number | ''>('');
  const [selectedStaffId, setSelectedStaffId] = useState<number | ''>('');
  const [aptType, setAptType] = useState<Appointment['type']>('consultation');
  const [slotDate, setSlotDate] = useState(tomorrowIsoDate());
  const [selectedSlot, setSelectedSlot] = useState('');
  const [notes, setNotes] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const appointmentsQuery = useQuery({
    queryKey: ['appointments'],
    queryFn: async () => (await appointmentsApi.list()).data,
  });

  const staffQuery = useQuery({
    queryKey: ['staff'],
    queryFn: async () => (await usersApi.listStaff()).data,
  });

  const patientsQuery = useQuery({
    queryKey: ['patients'],
    queryFn: async () => (await usersApi.listPatients()).data,
    enabled: !isPatient,
  });

  const effectiveStaffId =
    selectedStaffId !== '' ? selectedStaffId : (staffQuery.data?.[0]?.staff_id ?? '');
  const effectivePatientId = isPatient
    ? (user?.patient_id ?? '')
    : selectedPatientId !== ''
      ? selectedPatientId
      : (patientsQuery.data?.[0]?.patient_id ?? '');

  const availabilityQuery = useQuery({
    queryKey: ['availability', effectiveStaffId, slotDate],
    queryFn: async () =>
      (await appointmentsApi.getAvailability(Number(effectiveStaffId), slotDate)).data,
    enabled: showModal && effectiveStaffId !== '' && Boolean(slotDate),
  });

  const bookMutation = useMutation({
    mutationFn: (payload: Parameters<typeof appointmentsApi.book>[0]) =>
      appointmentsApi.book(payload),
    onSuccess: () => {
      setErrorMessage(null);
      setShowModal(false);
      setSelectedSlot('');
      setNotes('');
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
    onError: (err) => setErrorMessage(extractApiError(err, 'Could not book appointment.')),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: Appointment['status'] }) =>
      appointmentsApi.update(id, { status }),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
    onError: (err) => setErrorMessage(extractApiError(err, 'Could not update appointment.')),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) => appointmentsApi.cancel(id),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
    onError: (err) => setErrorMessage(extractApiError(err, 'Could not cancel appointment.')),
  });

  const availableSlots = availabilityQuery.data ?? [];
  const chosenSlot = selectedSlot || availableSlots[0] || '';

  const handleBook = (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectivePatientId || !effectiveStaffId || !chosenSlot) {
      setErrorMessage('Please select patient, clinician, and an available time slot.');
      return;
    }
    const startMs = new Date(chosenSlot).getTime();
    const endIso = new Date(startMs + 30 * 60000).toISOString();
    bookMutation.mutate({
      patient_id: Number(effectivePatientId),
      staff_id: Number(effectiveStaffId),
      type: aptType,
      start_time: chosenSlot,
      end_time: endIso,
      notes: notes.trim() || undefined,
    });
  };

  const appointments = appointmentsQuery.data ?? [];
  const bannerError =
    errorMessage || (appointmentsQuery.error ? extractApiError(appointmentsQuery.error) : null);

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
          type="button"
          onClick={() => {
            setErrorMessage(null);
            setShowModal(true);
          }}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition"
        >
          <Plus className="w-4 h-4" />
          New Appointment
        </button>
      </div>

      {bannerError && !showModal && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{bannerError}</span>
        </div>
      )}

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
            {appointmentsQuery.isLoading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  Loading appointments...
                </td>
              </tr>
            ) : appointments.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  No appointments scheduled yet.
                </td>
              </tr>
            ) : (
              appointments.map((apt) => (
                <tr key={apt.appointment_id} className="hover:bg-slate-50">
                  <td className="py-3.5 px-4 font-medium text-slate-900">
                    {apt.patient_name || `Patient #${apt.patient_id}`}
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="text-slate-900 capitalize">{apt.type}</div>
                    <div className="text-xs text-slate-500">
                      {apt.staff_name || `Staff #${apt.staff_id}`}
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-slate-600">{formatDateTime(apt.start_time)}</td>
                  <td className="py-3.5 px-4 text-slate-600">{apt.notes || '—'}</td>
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
                        {!isPatient && (
                          <button
                            type="button"
                            onClick={() =>
                              statusMutation.mutate({
                                id: apt.appointment_id,
                                status: 'completed',
                              })
                            }
                            title="Mark Completed"
                            aria-label={`Complete appointment ${apt.appointment_id}`}
                            className="text-emerald-600 hover:bg-emerald-50 p-1.5 rounded-lg"
                          >
                            <CheckCircle2 className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => cancelMutation.mutate(apt.appointment_id)}
                          title="Cancel"
                          aria-label={`Cancel appointment ${apt.appointment_id}`}
                          className="text-rose-600 hover:bg-rose-50 p-1.5 rounded-lg"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900">Schedule Appointment</h2>

            {errorMessage && (
              <div
                role="alert"
                className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700"
              >
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleBook} className="space-y-3.5">
              {!isPatient && (
                <div>
                  <label
                    htmlFor="apt-patient"
                    className="block text-xs font-medium text-slate-700 mb-1"
                  >
                    Patient
                  </label>
                  <select
                    id="apt-patient"
                    required
                    value={effectivePatientId}
                    onChange={(e) => setSelectedPatientId(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    {(patientsQuery.data ?? []).map((p) => (
                      <option key={p.patient_id} value={p.patient_id}>
                        {p.full_name} (#{p.patient_id})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label
                  htmlFor="apt-staff"
                  className="block text-xs font-medium text-slate-700 mb-1"
                >
                  Clinician
                </label>
                <select
                  id="apt-staff"
                  required
                  value={effectiveStaffId}
                  onChange={(e) => {
                    setSelectedStaffId(Number(e.target.value));
                    setSelectedSlot('');
                  }}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                >
                  {(staffQuery.data ?? []).map((s) => (
                    <option key={s.staff_id} value={s.staff_id}>
                      {s.full_name} ({s.staff_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="apt-type" className="block text-xs font-medium text-slate-700 mb-1">
                  Appointment Type
                </label>
                <select
                  id="apt-type"
                  value={aptType}
                  onChange={(e) => setAptType(e.target.value as Appointment['type'])}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                >
                  <option value="consultation">Orthopedic Consultation</option>
                  <option value="therapy">Rehabilitation / Physiotherapy</option>
                  <option value="imaging">Radiology / Imaging</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="apt-date"
                    className="block text-xs font-medium text-slate-700 mb-1"
                  >
                    Clinic Date
                  </label>
                  <input
                    id="apt-date"
                    type="date"
                    required
                    value={slotDate}
                    onChange={(e) => {
                      setSlotDate(e.target.value);
                      setSelectedSlot('');
                    }}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label
                    htmlFor="apt-slot"
                    className="block text-xs font-medium text-slate-700 mb-1"
                  >
                    Available 30-Min Slot
                  </label>
                  <select
                    id="apt-slot"
                    required
                    value={chosenSlot}
                    onChange={(e) => setSelectedSlot(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    {availableSlots.length === 0 ? (
                      <option value="">No free slots</option>
                    ) : (
                      availableSlots.map((slot) => (
                        <option key={slot} value={slot}>
                          {slot.slice(11, 16)} UTC
                        </option>
                      ))
                    )}
                  </select>
                </div>
              </div>

              <div>
                <label
                  htmlFor="apt-notes"
                  className="block text-xs font-medium text-slate-700 mb-1"
                >
                  Clinical Notes (Optional)
                </label>
                <input
                  id="apt-notes"
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
                  disabled={bookMutation.isPending || availableSlots.length === 0}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
                >
                  {bookMutation.isPending ? 'Booking...' : 'Confirm Booking'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
