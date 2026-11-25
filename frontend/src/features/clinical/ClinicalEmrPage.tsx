import React, { useState } from 'react';
import { FileCode2, Pill, HeartPulse, Plus } from 'lucide-react';
import { usePermissions } from '../../hooks/usePermissions';

interface Prescription {
  id: string;
  medication: string;
  dosage: string;
  frequency: string;
  prescribedBy: string;
  date: string;
}

const SAMPLE_HL7_ORU = `MSH|^~\\&|PACS_CDSS|MEDCORE_HOSP|EMR_CLIENT|MEDCORE|202611241430||ORU^R01|MSG00042|P|2.5
PID|1||MRN-884920^^^MEDCORE||Hassan^Omar||19950412|M|||12 Nile St^^Cairo^^11511
OBR|1|ORD-991|IMG-552|71046^Chest CT w/ Contrast^LN|||202611241410
OBX|1|TX|CDSS-AI^AI Radiology Finding^L||Right upper lobe pulmonary nodule (6.2mm) - Recommend follow-up||||||F`;

export const ClinicalEmrPage: React.FC = () => {
  const { isClinical } = usePermissions();
  const [activeTab, setActiveTab] = useState<'HISTORY' | 'PRESCRIPTIONS' | 'HL7'>('HISTORY');
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([
    {
      id: 'rx-1',
      medication: 'Amoxicillin / Clavulanate',
      dosage: '875mg / 125mg',
      frequency: 'Twice daily for 7 days',
      prescribedBy: 'Dr. Karim Nabil',
      date: '2026-11-20',
    },
  ]);
  const [medName, setMedName] = useState('');
  const [dosage, setDosage] = useState('');
  const [frequency, setFrequency] = useState('');

  const handleAddRx = (e: React.FormEvent) => {
    e.preventDefault();
    setPrescriptions([
      {
        id: `rx-${Date.now()}`,
        medication: medName,
        dosage,
        frequency,
        prescribedBy: 'Dr. Karim Nabil',
        date: new Date().toISOString().split('T')[0],
      },
      ...prescriptions,
    ]);
    setMedName('');
    setDosage('');
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
              MRN-884920
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Male • 31 yrs • Blood Type: O+ • Allergies: Penicillin
          </p>
        </div>

        <div className="flex gap-2">
          {(['HISTORY', 'PRESCRIPTIONS', 'HL7'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3.5 py-2 rounded-lg text-xs font-semibold transition ${
                activeTab === tab
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {tab === 'HISTORY' && 'Medical History & Vitals'}
              {tab === 'PRESCRIPTIONS' && 'Prescriptions'}
              {tab === 'HL7' && 'HL7 v2.5 Feed'}
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
              Latest Vitals
            </h2>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">Blood Pressure</span>
                <span className="font-bold text-slate-900">122 / 78 mmHg</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">Heart Rate</span>
                <span className="font-bold text-slate-900">74 bpm</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">SpO2</span>
                <span className="font-bold text-slate-900">98%</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-xs text-slate-500 block">Temperature</span>
                <span className="font-bold text-slate-900">36.8 °C</span>
              </div>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
            <h2 className="font-semibold text-slate-900">Clinical Encounter Notes</h2>
            <div className="p-3.5 border border-slate-100 rounded-lg bg-slate-50 text-sm space-y-1">
              <div className="flex justify-between text-xs text-slate-500">
                <span>Radiology Consultation</span>
                <span>Nov 20, 2026</span>
              </div>
              <p className="text-slate-700">
                Patient referred for high-resolution chest CT due to persistent dry cough. DICOM
                study uploaded and queued for CDSS nodule analysis.
              </p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'PRESCRIPTIONS' && (
        <div className="bg-white p-5 rounded-xl border border-slate-200 space-y-5">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Pill className="w-4 h-4 text-blue-600" />
            Active Treatment & Prescriptions
          </h2>

          {isClinical && (
            <form
              onSubmit={handleAddRx}
              className="grid sm:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-lg"
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
                placeholder="Dosage (e.g., 500mg)"
                value={dosage}
                onChange={(e) => setDosage(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
              />
              <input
                required
                placeholder="Frequency"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
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
                    {rx.medication} <span className="text-blue-600">({rx.dosage})</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {rx.frequency} • Prescribed by {rx.prescribedBy}
                  </p>
                </div>
                <span className="text-xs text-slate-400">{rx.date}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'HL7' && (
        <div className="bg-slate-900 text-emerald-400 p-5 rounded-xl font-mono text-xs overflow-x-auto space-y-3">
          <div className="flex items-center justify-between text-slate-400 border-b border-slate-800 pb-2">
            <span className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-blue-400" />
              HL7 v2.5 ORU^R01 Diagnostic Observation Message
            </span>
            <span className="text-emerald-400">ACK: AA (Interoperability Verified)</span>
          </div>
          <pre className="leading-relaxed">{SAMPLE_HL7_ORU}</pre>
        </div>
      )}
    </div>
  );
};
