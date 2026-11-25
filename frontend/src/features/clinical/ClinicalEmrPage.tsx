import React, { useState } from 'react';
import { FileCode2, Pill, HeartPulse, Plus } from 'lucide-react';
import { usePermissions } from '../../hooks/usePermissions';

interface PrescriptionItem {
  id: number;
  medication: string;
  dose: string;
  frequency: string;
  duration: string;
  prescribedBy: string;
  date: string;
}

const SAMPLE_HL7_FHIR = `{
  "resourceType": "Condition",
  "clinicalStatus": { "coding": [{ "code": "active" }] },
  "code": {
    "coding": [{
      "system": "http://hl7.org/fhir/sid/icd-10",
      "code": "S83.511A",
      "display": "Sprain of anterior cruciate ligament of right knee"
    }]
  },
  "subject": { "reference": "Patient/101", "display": "Omar Hassan" },
  "recorder": { "reference": "Practitioner/10", "display": "Dr. Karim Nabil" }
}`;

export const ClinicalEmrPage: React.FC = () => {
  const { isStaff } = usePermissions();
  const [activeTab, setActiveTab] = useState<'HISTORY' | 'PRESCRIPTIONS' | 'FHIR'>('HISTORY');
  const [prescriptions, setPrescriptions] = useState<PrescriptionItem[]>([
    {
      id: 1,
      medication: 'Celecoxib',
      dose: '200 mg',
      frequency: 'Once daily',
      duration: '14 days',
      prescribedBy: 'Dr. Karim Nabil',
      date: '2026-11-20',
    },
  ]);
  const [medName, setMedName] = useState('');
  const [dose, setDose] = useState('');
  const [frequency, setFrequency] = useState('');
  const [duration, setDuration] = useState('7 days');

  const handleAddRx = (e: React.FormEvent) => {
    e.preventDefault();
    setPrescriptions([
      {
        id: Date.now(),
        medication: medName,
        dose,
        frequency,
        duration,
        prescribedBy: 'Dr. Karim Nabil',
        date: new Date().toISOString().split('T')[0],
      },
      ...prescriptions,
    ]);
    setMedName('');
    setDose('');
    setFrequency('');
  };

  return (
    <div className="space-y-6">
      {/* Patient Banner */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900">Omar Hassan</h1>
            <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
              PAT-101
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Male • 31 yrs • Affected Area: Right Knee • ICD-10: S83.511A
          </p>
        </div>

        <div className="flex gap-2">
          {(['HISTORY', 'PRESCRIPTIONS', 'FHIR'] as const).map((tab) => (
            <button
              key={tab}
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

      {/* Tab Content */}
      {activeTab === 'HISTORY' && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2">
              <HeartPulse className="w-4 h-4 text-rose-500" />
              Orthopedic Assessment
            </h2>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">Affected Area</span>
                <span className="font-bold text-slate-900">Right Knee (ACL)</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">Active Flexion ROM</span>
                <span className="font-bold text-slate-900">112°</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">Pain Score</span>
                <span className="font-bold text-slate-900">2 / 10</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">ICD-10 Code</span>
                <span className="font-bold text-indigo-600">S83.511A</span>
              </div>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <h2 className="font-semibold text-slate-900">Clinical Encounter Notes</h2>
            <div className="p-3.5 border border-slate-100 rounded-lg bg-slate-50 text-sm space-y-1">
              <div className="flex justify-between text-xs text-slate-500">
                <span>Orthopedic Follow-Up</span>
                <span>Nov 20, 2026</span>
              </div>
              <p className="text-slate-700">
                Patient recovering well post-arthroscopic ACL reconstruction. Knee MRI uploaded to
                Orthanc PACS for CDSS graft integrity assessment.
              </p>
            </div>
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
              className="grid sm:grid-cols-5 gap-3 bg-slate-50 p-4 rounded-lg"
            >
              <input
                required
                placeholder="Medication name"
                value={medName}
                onChange={(e) => setMedName(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <input
                required
                placeholder="Dose (e.g., 200mg)"
                value={dose}
                onChange={(e) => setDose(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <input
                required
                placeholder="Frequency"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <input
                required
                placeholder="Duration"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <button
                type="submit"
                className="flex items-center justify-center gap-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              >
                <Plus className="w-4 h-4" />
                Prescribe
              </button>
            </form>
          )}

          <div className="divide-y divide-slate-100">
            {prescriptions.map((rx) => (
              <div key={rx.id} className="py-3 flex items-center justify-between text-sm">
                <div>
                  <p className="font-semibold text-slate-900">
                    {rx.medication} <span className="text-blue-600">({rx.dose})</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {rx.frequency} • {rx.duration} • Prescribed by {rx.prescribedBy}
                  </p>
                </div>
                <span className="text-xs text-slate-400">{rx.date}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'FHIR' && (
        <div className="bg-slate-900 text-emerald-400 p-5 rounded-xl font-mono text-xs overflow-x-auto space-y-3">
          <div className="flex items-center justify-between text-slate-400 border-b border-slate-800 pb-2">
            <span className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-blue-400" />
              HL7 FHIR R4 Condition Resource (/api/v1/fhir/Condition)
            </span>
            <span className="text-emerald-400">FHIR R4 Validated</span>
          </div>
          <pre className="leading-relaxed">{SAMPLE_HL7_FHIR}</pre>
        </div>
      )}
    </div>
  );
};
