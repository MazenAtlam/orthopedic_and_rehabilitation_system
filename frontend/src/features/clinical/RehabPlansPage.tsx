import React, { useState } from 'react';
import { Dumbbell, Plus, TrendingUp } from 'lucide-react';
import type { RehabSession, TreatmentPlan } from '../../types';
import { usePermissions } from '../../hooks/usePermissions';

export const RehabPlansPage: React.FC = () => {
  const { isStaff } = usePermissions();
  const [plans] = useState<TreatmentPlan[]>([
    {
      plan_id: 1,
      patient_id: 101,
      staff_id: 10,
      title: 'Post-Op ACL Reconstruction Rehab (Phase II)',
      goal: 'Achieve 120° knee flexion and pain-free single-leg stance',
      start_date: '2026-11-01',
      end_date: '2026-12-30',
      status: 'active',
    },
  ]);

  const [sessions, setSessions] = useState<RehabSession[]>([
    {
      session_id: 1,
      plan_id: 1,
      session_date: '2026-11-18',
      exercises: 'Heel slides, Quad sets, Stationary bike (15 min)',
      pain_score: 4,
      range_of_motion: 95,
      notes: 'Good tolerance, mild swelling post-session',
    },
    {
      session_id: 2,
      plan_id: 1,
      session_date: '2026-11-22',
      exercises: 'Mini-squats, Step-ups, Hamstring curls',
      pain_score: 2,
      range_of_motion: 112,
      notes: 'Significant improvement in active flexion',
    },
  ]);

  const [exercises, setExercises] = useState('');
  const [painScore, setPainScore] = useState(3);
  const [rom, setRom] = useState(115);
  const [notes, setNotes] = useState('');

  const handleLogSession = (e: React.FormEvent) => {
    e.preventDefault();
    setSessions([
      {
        session_id: Date.now(),
        plan_id: 1,
        session_date: new Date().toISOString().split('T')[0],
        exercises,
        pain_score: painScore,
        range_of_motion: rom,
        notes,
      },
      ...sessions,
    ]);
    setExercises('');
    setNotes('');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Rehabilitation Plans & Sessions</h1>
        <p className="text-sm text-slate-500">
          Orthopedic physiotherapy progress, pain scores (0–10), and range of motion tracking
        </p>
      </div>

      {/* Active Treatment Plan Card */}
      {plans.map((plan) => (
        <div
          key={plan.plan_id}
          className="bg-white p-5 rounded-xl border border-slate-200 space-y-2"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Dumbbell className="w-5 h-5 text-blue-600" />
              {plan.title}
            </h2>
            <span className="text-xs uppercase font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700">
              {plan.status}
            </span>
          </div>
          <p className="text-sm text-slate-700">
            <strong>Clinical Goal:</strong> {plan.goal}
          </p>
          <p className="text-xs text-slate-500">
            Period: {plan.start_date} to {plan.end_date}
          </p>
        </div>
      ))}

      {/* Staff: Log New Rehab Session */}
      {isStaff && (
        <form
          onSubmit={handleLogSession}
          className="bg-white p-5 rounded-xl border border-slate-200 grid sm:grid-cols-4 gap-3 items-end"
        >
          <div className="sm:col-span-2">
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Exercises Performed
            </label>
            <input
              required
              placeholder="e.g., Wall sits, Resistance band abduction"
              value={exercises}
              onChange={(e) => setExercises(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Pain Score (0–10)
            </label>
            <input
              type="number"
              min={0}
              max={10}
              required
              value={painScore}
              onChange={(e) => setPainScore(Number(e.target.value))}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Range of Motion (°)
            </label>
            <input
              type="number"
              min={0}
              max={180}
              required
              value={rom}
              onChange={(e) => setRom(Number(e.target.value))}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div className="sm:col-span-3">
            <input
              placeholder="Session notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <button
            type="submit"
            className="flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Log Session
          </button>
        </form>
      )}

      {/* Session History */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center gap-2 font-semibold text-sm text-slate-900">
          <TrendingUp className="w-4 h-4 text-teal-600" />
          Logged Therapy Sessions
        </div>
        <div className="divide-y divide-slate-100">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className="p-4 flex flex-wrap items-center justify-between gap-4 text-sm"
            >
              <div>
                <p className="font-semibold text-slate-900">{s.exercises}</p>
                <p className="text-xs text-slate-500">
                  {s.session_date} {s.notes ? `• ${s.notes}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 text-xs font-semibold">
                  Pain: {s.pain_score}/10
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-800 text-xs font-semibold">
                  ROM: {s.range_of_motion}°
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
