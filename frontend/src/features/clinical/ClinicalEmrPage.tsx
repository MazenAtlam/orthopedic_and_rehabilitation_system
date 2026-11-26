import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileCode2, Pill, HeartPulse, Plus, AlertCircle } from 'lucide-react';
import { extractApiError } from '../../api/client';
import { billingApi, clinicalApi, fhirApi, usersApi } from '../../api/endpoints';
import { usePermissions } from '../../hooks/usePermissions';
import { formatDate } from '../../utils/formatters';

export const ClinicalEmrPage: React.FC = () => {
  const { user, isStaff } = usePermissions();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'HISTORY' | 'PRESCRIPTIONS' | 'FHIR'>('HISTORY');
  const [selectedPatientId, setSelectedPatientId] = useState<number | ''>('');
  const [fhirResource, setFhirResource] = useState<'Condition' | 'Encounter' | 'MedicationRequest'>(
    'Condition',
  );

  // Visit record form
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [affectedArea, setAffectedArea] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [icdSearch, setIcdSearch] = useState('');
  const [selectedIcd, setSelectedIcd] = useState('');
  const [notes, setNotes] = useState('');

  // Prescription form
  const [rxRecordId, setRxRecordId] = useState<number | ''>('');
  const [medName, setMedName] = useState('');
  const [dose, setDose] = useState('');
  const [frequency, setFrequency] = useState('');
  const [duration, setDuration] = useState('7 days');
  const [instructions, setInstructions] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const patientsQuery = useQuery({
    queryKey: ['patients'],
    queryFn: async () => (await usersApi.listPatients()).data,
    enabled: isStaff,
  });

  const effectivePatientId = isStaff
    ? selectedPatientId !== ''
      ? selectedPatientId
      : (patientsQuery.data?.[0]?.patient_id ?? null)
    : (user?.patient_id ?? null);

  const patientProfileQuery = useQuery({
    queryKey: ['patient', effectivePatientId],
    queryFn: async () => (await usersApi.getPatient(Number(effectivePatientId))).data,
    enabled: Boolean(effectivePatientId),
  });

  const recordsQuery = useQuery({
    queryKey: ['records', effectivePatientId],
    queryFn: async () => (await clinicalApi.getPatientRecords(Number(effectivePatientId))).data,
    enabled: Boolean(effectivePatientId),
  });

  const prescriptionsQuery = useQuery({
    queryKey: ['prescriptions', effectivePatientId],
    queryFn: async () =>
      (await clinicalApi.getPatientPrescriptions(Number(effectivePatientId))).data,
    enabled: Boolean(effectivePatientId),
  });

  const icdQuery = useQuery({
    queryKey: ['icd10', icdSearch],
    queryFn: async () => (await billingApi.searchIcd10(icdSearch)).data,
    enabled: isStaff,
  });

  const fhirQuery = useQuery({
    queryKey: ['fhir', fhirResource, effectivePatientId],
    queryFn: async () =>
      (
        await fhirApi.searchResource(fhirResource, {
          patient: `Patient/${effectivePatientId}`,
        })
      ).data,
    enabled: activeTab === 'FHIR' && Boolean(effectivePatientId),
  });

  const createRecordMutation = useMutation({
    mutationFn: (payload: Parameters<typeof clinicalApi.createRecord>[0]) =>
      clinicalApi.createRecord(payload),
    onSuccess: () => {
      setActionError(null);
      setChiefComplaint('');
      setAffectedArea('');
      setDiagnosis('');
      setNotes('');
      queryClient.invalidateQueries({ queryKey: ['records', effectivePatientId] });
      queryClient.invalidateQueries({ queryKey: ['fhir'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to save clinical record.')),
  });

  const addRxMutation = useMutation({
    mutationFn: ({
      recordId,
      data,
    }: {
      recordId: number;
      data: Parameters<typeof clinicalApi.addPrescription>[1];
    }) => clinicalApi.addPrescription(recordId, data),
    onSuccess: () => {
      setActionError(null);
      setMedName('');
      setDose('');
      setFrequency('');
      setInstructions('');
      queryClient.invalidateQueries({ queryKey: ['prescriptions', effectivePatientId] });
      queryClient.invalidateQueries({ queryKey: ['fhir'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to add prescription.')),
  });

  const records = recordsQuery.data ?? [];
  const prescriptions = prescriptionsQuery.data ?? [];
  const icdCodes = icdQuery.data ?? [];
  const effectiveIcd = selectedIcd || icdCodes[0]?.code || '';
  const effectiveRecordForRx = rxRecordId !== '' ? rxRecordId : (records[0]?.record_id ?? '');

  const handleCreateRecord = (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectivePatientId) return;
    createRecordMutation.mutate({
      patient_id: Number(effectivePatientId),
      chief_complaint: chiefComplaint.trim() || null,
      affected_area: affectedArea.trim() || null,
      diagnosis: diagnosis.trim() || null,
      icd10_code: effectiveIcd || null,
      notes: notes.trim() || null,
    });
  };

  const handleAddRx = (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectiveRecordForRx) {
      setActionError('Create a clinical visit record for this patient before prescribing.');
      return;
    }
    addRxMutation.mutate({
      recordId: Number(effectiveRecordForRx),
      data: {
        medication: medName.trim(),
        dose: dose.trim() || null,
        frequency: frequency.trim() || null,
        duration: duration.trim() || null,
        instructions: instructions.trim() || null,
      },
    });
  };

  const patientProfile = patientProfileQuery.data;
  const latestRecord = records[0];

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            {isStaff && (patientsQuery.data ?? []).length > 0 ? (
              <select
                aria-label="Select patient"
                value={effectivePatientId ?? ''}
                onChange={(e) => {
                  setSelectedPatientId(Number(e.target.value));
                  setRxRecordId('');
                }}
                className="text-base font-bold text-slate-900 border border-slate-300 rounded-lg px-3 py-1.5 bg-white"
              >
                {(patientsQuery.data ?? []).map((p) => (
                  <option key={p.patient_id} value={p.patient_id}>
                    {p.full_name} (PAT-{p.patient_id})
                  </option>
                ))}
              </select>
            ) : (
              <h1 className="text-xl font-bold text-slate-900">
                {patientProfile?.full_name || user?.full_name || 'Patient Chart'}
              </h1>
            )}
            {effectivePatientId && (
              <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                PAT-{effectivePatientId}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500">
            {patientProfile
              ? `${patientProfile.gender} • DOB ${patientProfile.birth_date}`
              : 'Loading patient demographics...'}
            {latestRecord?.icd10_code ? ` • Latest ICD-10: ${latestRecord.icd10_code}` : ''}
          </p>
        </div>

        <div className="flex gap-2">
          {(['HISTORY', 'PRESCRIPTIONS', 'FHIR'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`px-3.5 py-2 rounded-lg text-xs font-semibold transition ${
                activeTab === tab
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {tab === 'HISTORY' && 'Musculoskeletal EMR'}
              {tab === 'PRESCRIPTIONS' && 'Prescriptions'}
              {tab === 'FHIR' && 'HL7 FHIR R4 Payload'}
            </button>
          ))}
        </div>
      </div>

      {actionError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {activeTab === 'HISTORY' && (
        <div className="space-y-6">
          {isStaff && (
            <form
              onSubmit={handleCreateRecord}
              className="bg-white p-5 rounded-xl border border-slate-200 space-y-3"
            >
              <h2 className="font-semibold text-slate-900 flex items-center gap-2 text-sm">
                <HeartPulse className="w-4 h-4 text-rose-500" />
                Record New Orthopedic Visit
              </h2>
              <div className="grid sm:grid-cols-4 gap-3">
                <input
                  required
                  placeholder="Chief complaint (e.g., Left knee pain)"
                  value={chiefComplaint}
                  onChange={(e) => setChiefComplaint(e.target.value)}
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
                <input
                  placeholder="Affected area (e.g., Right Knee)"
                  value={affectedArea}
                  onChange={(e) => setAffectedArea(e.target.value)}
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
                <input
                  required
                  placeholder="Clinical diagnosis"
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
                <input
                  placeholder="Search ICD-10 (e.g., M17 or knee)"
                  value={icdSearch}
                  onChange={(e) => {
                    setIcdSearch(e.target.value);
                    setSelectedIcd('');
                  }}
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
                />
              </div>
              <div className="grid sm:grid-cols-4 gap-3 items-end">
                <div className="sm:col-span-2">
                  <label
                    htmlFor="emr-icd-select"
                    className="block text-xs font-medium text-slate-600 mb-1"
                  >
                    ICD-10 Code
                  </label>
                  <select
                    id="emr-icd-select"
                    value={effectiveIcd}
                    onChange={(e) => setSelectedIcd(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                  >
                    <option value="">None</option>
                    {icdCodes.map((code) => (
                      <option key={code.code} value={code.code}>
                        {code.code} — {code.description}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <input
                    placeholder="Encounter notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
                  />
                </div>
                <button
                  type="submit"
                  disabled={createRecordMutation.isPending}
                  className="flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2 px-4 rounded-lg text-sm font-medium"
                >
                  <Plus className="w-4 h-4" />
                  Save Visit
                </button>
              </div>
            </form>
          )}

          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <h2 className="font-semibold text-slate-900">Clinical Encounter History</h2>
            {recordsQuery.isLoading ? (
              <p className="text-sm text-slate-500">Loading clinical records...</p>
            ) : records.length === 0 ? (
              <p className="text-sm text-slate-500">No clinical encounters recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {records.map((rec) => (
                  <div
                    key={rec.record_id}
                    className="p-4 border border-slate-100 rounded-lg bg-slate-50 text-sm space-y-1.5"
                  >
                    <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
                      <span>
                        Visit #{rec.record_id} • {rec.staff_name || `Clinician #${rec.staff_id}`}
                      </span>
                      <span>{formatDate(rec.visit_date)}</span>
                    </div>
                    <p className="font-semibold text-slate-900">
                      {rec.diagnosis || rec.chief_complaint || 'Orthopedic Encounter'}
                      {rec.affected_area ? ` (${rec.affected_area})` : ''}
                    </p>
                    {rec.icd10_code && (
                      <p className="text-xs font-mono text-indigo-600">
                        ICD-10: {rec.icd10_code}
                        {rec.icd10_description ? ` — ${rec.icd10_description}` : ''}
                      </p>
                    )}
                    {rec.notes && <p className="text-slate-700 text-xs">{rec.notes}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'PRESCRIPTIONS' && (
        <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-5">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Pill className="w-4 h-4 text-blue-600" />
            Active Medications & Prescriptions
          </h2>

          {isStaff && (
            <form
              onSubmit={handleAddRx}
              className="grid sm:grid-cols-6 gap-3 bg-slate-50 p-4 rounded-lg items-end"
            >
              <div>
                <label
                  htmlFor="rx-record"
                  className="block text-xs font-medium text-slate-600 mb-1"
                >
                  Visit Record
                </label>
                <select
                  id="rx-record"
                  value={effectiveRecordForRx}
                  onChange={(e) => setRxRecordId(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
                >
                  {records.length === 0 ? (
                    <option value="">No visits yet</option>
                  ) : (
                    records.map((r) => (
                      <option key={r.record_id} value={r.record_id}>
                        #{r.record_id} ({r.visit_date})
                      </option>
                    ))
                  )}
                </select>
              </div>
              <input
                required
                placeholder="Medication name"
                value={medName}
                onChange={(e) => setMedName(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <input
                placeholder="Dose (e.g., 200mg)"
                value={dose}
                onChange={(e) => setDose(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <input
                placeholder="Frequency"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <input
                placeholder="Duration"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <button
                type="submit"
                disabled={addRxMutation.isPending || records.length === 0}
                className="flex items-center justify-center gap-1.5 bg-blue-600 text-white py-2 px-3 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
              >
                <Plus className="w-4 h-4" />
                Prescribe
              </button>
            </form>
          )}

          {prescriptions.length === 0 ? (
            <p className="text-sm text-slate-500">No prescriptions issued for this patient.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {prescriptions.map((rx) => (
                <div
                  key={rx.prescription_id}
                  className="py-3 flex items-center justify-between text-sm"
                >
                  <div>
                    <p className="font-semibold text-slate-900">
                      {rx.medication}{' '}
                      {rx.dose && <span className="text-blue-600">({rx.dose})</span>}
                    </p>
                    <p className="text-xs text-slate-500">
                      {[rx.frequency, rx.duration, rx.instructions].filter(Boolean).join(' • ') ||
                        `Visit #${rx.record_id}`}
                    </p>
                  </div>
                  <span className="text-xs text-slate-400">
                    {rx.created_at ? formatDate(rx.created_at) : `Record #${rx.record_id}`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'FHIR' && (
        <div className="bg-slate-900 text-emerald-400 p-5 rounded-xl font-mono text-xs overflow-x-auto space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-slate-400 border-b border-slate-800 pb-2">
            <span className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-blue-400" />
              Live HL7 FHIR R4 Bundle (/api/v1/fhir/{fhirResource}?patient=Patient/
              {effectivePatientId})
            </span>
            <select
              aria-label="FHIR resource type"
              value={fhirResource}
              onChange={(e) =>
                setFhirResource(e.target.value as 'Condition' | 'Encounter' | 'MedicationRequest')
              }
              className="bg-slate-800 text-slate-200 border border-slate-700 rounded px-2 py-1 text-xs"
            >
              <option value="Condition">Condition</option>
              <option value="Encounter">Encounter</option>
              <option value="MedicationRequest">MedicationRequest</option>
            </select>
          </div>
          <pre className="leading-relaxed">
            {fhirQuery.isLoading
              ? 'Loading FHIR R4 bundle...'
              : JSON.stringify(fhirQuery.data ?? {}, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
