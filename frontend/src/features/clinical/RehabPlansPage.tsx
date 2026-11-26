import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Dumbbell, Plus, TrendingUp, AlertCircle } from 'lucide-react';
import { extractApiError } from '../../api/client';
import { rehabApi, usersApi } from '../../api/endpoints';
import { usePermissions } from '../../hooks/usePermissions';
import type { TreatmentPlan } from '../../types';

export const RehabPlansPage: React.FC = () => {
  const { isStaff } = usePermissions();
  const queryClient = useQueryClient();

  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [planPatientId, setPlanPatientId] = useState<number | ''>('');
  const [planTitle, setPlanTitle] = useState('');
  const [planGoal, setPlanGoal] = useState('');
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState('');

  const [exercises, setExercises] = useState('');
  const [painScore, setPainScore] = useState(3);
  const [rom, setRom] = useState(110);
  const [notes, setNotes] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const plansQuery = useQuery({
    queryKey: ['treatment-plans'],
    queryFn: async () => (await rehabApi.listPlans()).data,
  });

  const patientsQuery = useQuery({
    queryKey: ['patients'],
    queryFn: async () => (await usersApi.listPatients()).data,
    enabled: isStaff,
  });

  const plans = plansQuery.data ?? [];
  const activePlanId = selectedPlanId ?? plans[0]?.plan_id ?? null;

  const sessionsQuery = useQuery({
    queryKey: ['rehab-sessions', activePlanId],
    queryFn: async () => (await rehabApi.listSessions(Number(activePlanId))).data,
    enabled: Boolean(activePlanId),
  });

  const createPlanMutation = useMutation({
    mutationFn: (payload: Parameters<typeof rehabApi.createPlan>[0]) =>
      rehabApi.createPlan(payload),
    onSuccess: (res) => {
      setActionError(null);
      setShowPlanForm(false);
      setPlanTitle('');
      setPlanGoal('');
      setEndDate('');
      setSelectedPlanId(res.data.plan_id);
      queryClient.invalidateQueries({ queryKey: ['treatment-plans'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to create treatment plan.')),
  });

  const updatePlanMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: TreatmentPlan['status'] }) =>
      rehabApi.updatePlan(id, { status }),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['treatment-plans'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to update treatment plan.')),
  });

  const logSessionMutation = useMutation({
    mutationFn: ({
      planId,
      data,
    }: {
      planId: number;
      data: Parameters<typeof rehabApi.logSession>[1];
    }) => rehabApi.logSession(planId, data),
    onSuccess: () => {
      setActionError(null);
      setExercises('');
      setNotes('');
      queryClient.invalidateQueries({ queryKey: ['rehab-sessions', activePlanId] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to log rehab session.')),
  });

  const effectivePatientForPlan =
    planPatientId !== '' ? planPatientId : (patientsQuery.data?.[0]?.patient_id ?? '');

  const handleCreatePlan = (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectivePatientForPlan) return;
    createPlanMutation.mutate({
      patient_id: Number(effectivePatientForPlan),
      title: planTitle.trim(),
      goal: planGoal.trim() || null,
      start_date: startDate,
      end_date: endDate || null,
    });
  };

  const handleLogSession = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activePlanId) return;
    logSessionMutation.mutate({
      planId: activePlanId,
      data: {
        exercises: exercises.trim(),
        pain_score: painScore,
        range_of_motion: rom,
        notes: notes.trim() || null,
      },
    });
  };

  const sessions = sessionsQuery.data ?? [];
  const trendData = [...sessions].reverse().map((s) => ({
    date: s.session_date.slice(5),
    rom: s.range_of_motion ?? 0,
    pain: s.pain_score ?? 0,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Rehabilitation Plans & Sessions</h1>
          <p className="text-sm text-slate-500">
            Orthopedic physiotherapy progress, pain scores (0–10), and range of motion tracking
          </p>
        </div>

        {isStaff && (
          <button
            type="button"
            onClick={() => setShowPlanForm((v) => !v)}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Treatment Plan
          </button>
        )}
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

      {isStaff && showPlanForm && (
        <form
          onSubmit={handleCreatePlan}
          className="bg-white p-5 rounded-xl border border-slate-200 grid sm:grid-cols-5 gap-3 items-end"
        >
          <div>
            <label htmlFor="plan-patient" className="block text-xs font-medium text-slate-700 mb-1">
              Patient
            </label>
            <select
              id="plan-patient"
              value={effectivePatientForPlan}
              onChange={(e) => setPlanPatientId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
            >
              {(patientsQuery.data ?? []).map((p) => (
                <option key={p.patient_id} value={p.patient_id}>
                  {p.full_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="plan-title" className="block text-xs font-medium text-slate-700 mb-1">
              Plan Title
            </label>
            <input
              id="plan-title"
              required
              placeholder="ACL Reconstruction Rehab"
              value={planTitle}
              onChange={(e) => setPlanTitle(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label htmlFor="plan-goal" className="block text-xs font-medium text-slate-700 mb-1">
              Clinical Goal
            </label>
            <input
              id="plan-goal"
              placeholder="Restore 120° flexion"
              value={planGoal}
              onChange={(e) => setPlanGoal(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="plan-start" className="block text-xs font-medium text-slate-700 mb-1">
                Start
              </label>
              <input
                id="plan-start"
                type="date"
                required
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-2 py-2 border border-slate-300 rounded-lg text-xs"
              />
            </div>
            <div>
              <label htmlFor="plan-end" className="block text-xs font-medium text-slate-700 mb-1">
                End
              </label>
              <input
                id="plan-end"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-2 py-2 border border-slate-300 rounded-lg text-xs"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={createPlanMutation.isPending}
            className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium"
          >
            Save Plan
          </button>
        </form>
      )}

      {plans.length === 0 ? (
        <div className="bg-white p-6 rounded-xl border border-slate-200 text-sm text-slate-500">
          {plansQuery.isLoading ? 'Loading treatment plans...' : 'No treatment plans assigned yet.'}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {plans.map((plan) => {
            const isSelected = plan.plan_id === activePlanId;
            return (
              <div
                key={plan.plan_id}
                onClick={() => setSelectedPlanId(plan.plan_id)}
                className={`bg-white p-5 rounded-xl border cursor-pointer transition space-y-2 ${
                  isSelected ? 'border-blue-500 ring-1 ring-blue-500' : 'border-slate-200'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Dumbbell className="w-5 h-5 text-blue-600" />
                    {plan.title}
                  </h2>
                  {isStaff ? (
                    <select
                      aria-label={`Status for ${plan.title}`}
                      value={plan.status}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) =>
                        updatePlanMutation.mutate({
                          id: plan.plan_id,
                          status: e.target.value as TreatmentPlan['status'],
                        })
                      }
                      className="text-xs uppercase font-semibold px-2 py-1 rounded-lg border border-slate-200 bg-slate-50"
                    >
                      <option value="active">active</option>
                      <option value="completed">completed</option>
                      <option value="stopped">stopped</option>
                    </select>
                  ) : (
                    <span className="text-xs uppercase font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700">
                      {plan.status}
                    </span>
                  )}
                </div>
                {plan.goal && (
                  <p className="text-sm text-slate-700">
                    <strong>Clinical Goal:</strong> {plan.goal}
                  </p>
                )}
                <p className="text-xs text-slate-500">
                  {plan.patient_name ? `${plan.patient_name} • ` : ''}
                  Period: {plan.start_date}
                  {plan.end_date ? ` to ${plan.end_date}` : ''}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {isStaff && activePlanId && (
        <form
          onSubmit={handleLogSession}
          className="bg-white p-5 rounded-xl border border-slate-200 grid sm:grid-cols-4 gap-3 items-end"
        >
          <div className="sm:col-span-2">
            <label
              htmlFor="session-exercises"
              className="block text-xs font-medium text-slate-700 mb-1"
            >
              Exercises Performed
            </label>
            <input
              id="session-exercises"
              required
              placeholder="e.g., Wall sits, Resistance band abduction"
              value={exercises}
              onChange={(e) => setExercises(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label htmlFor="session-pain" className="block text-xs font-medium text-slate-700 mb-1">
              Pain Score (0–10)
            </label>
            <input
              id="session-pain"
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
            <label htmlFor="session-rom" className="block text-xs font-medium text-slate-700 mb-1">
              Range of Motion (°)
            </label>
            <input
              id="session-rom"
              type="number"
              min={0}
              max={360}
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
            disabled={logSessionMutation.isPending}
            className="flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2 px-4 rounded-lg text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Log Session
          </button>
        </form>
      )}

      {trendData.length > 1 && (
        <div className="bg-white p-5 rounded-xl border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-900 mb-3">ROM (°) & Pain Progression</h3>
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line type="monotone" dataKey="rom" stroke="#2563eb" strokeWidth={2} name="ROM °" />
                <Line
                  type="monotone"
                  dataKey="pain"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  name="Pain /10"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center gap-2 font-semibold text-sm text-slate-900">
          <TrendingUp className="w-4 h-4 text-teal-600" />
          Logged Therapy Sessions
        </div>
        <div className="divide-y divide-slate-100">
          {sessions.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">No therapy sessions logged for this plan.</p>
          ) : (
            sessions.map((s) => (
              <div
                key={s.session_id}
                className="p-4 flex flex-wrap items-center justify-between gap-4 text-sm"
              >
                <div>
                  <p className="font-semibold text-slate-900">
                    {s.exercises || 'Physiotherapy Session'}
                  </p>
                  <p className="text-xs text-slate-500">
                    {s.session_date} {s.notes ? `• ${s.notes}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {s.pain_score !== null && (
                    <span className="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 text-xs font-semibold">
                      Pain: {s.pain_score}/10
                    </span>
                  )}
                  {s.range_of_motion !== null && (
                    <span className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-800 text-xs font-semibold">
                      ROM: {s.range_of_motion}°
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
