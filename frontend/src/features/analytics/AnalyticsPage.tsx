import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Users, CalendarCheck, DollarSign, Activity, AlertCircle } from 'lucide-react';
import { extractApiError } from '../../api/client';
import { appointmentsApi, billingApi, rehabApi, reportsApi } from '../../api/endpoints';
import { usePermissions } from '../../hooks/usePermissions';
import { formatCurrency, toAmount } from '../../utils/formatters';

function defaultDateRange(): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * 86400000);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

export const AnalyticsPage: React.FC = () => {
  const { isAdmin, isStaff, isPatient } = usePermissions();
  const initialRange = defaultDateRange();
  const [startDate, setStartDate] = useState(initialRange.start);
  const [endDate, setEndDate] = useState(initialRange.end);

  const systemQuery = useQuery({
    queryKey: ['reports', 'system', startDate, endDate],
    queryFn: async () => (await reportsApi.getSystem({ start: startDate, end: endDate })).data,
    enabled: isAdmin,
  });

  const patientReportQuery = useQuery({
    queryKey: ['reports', 'patients', startDate, endDate],
    queryFn: async () => (await reportsApi.getPatients({ start: startDate, end: endDate })).data,
    enabled: isAdmin || isStaff,
  });

  const financialQuery = useQuery({
    queryKey: ['reports', 'financial', startDate, endDate],
    queryFn: async () => (await reportsApi.getFinancial({ start: startDate, end: endDate })).data,
    enabled: isAdmin,
  });

  const appointmentsQuery = useQuery({
    queryKey: ['appointments', 'dashboard'],
    queryFn: async () => (await appointmentsApi.list()).data,
    enabled: isStaff || isPatient,
  });

  const plansQuery = useQuery({
    queryKey: ['treatment-plans', 'dashboard'],
    queryFn: async () => (await rehabApi.listPlans()).data,
    enabled: isStaff || isPatient,
  });

  const invoicesQuery = useQuery({
    queryKey: ['invoices', 'dashboard'],
    queryFn: async () => (await billingApi.listInvoices()).data,
    enabled: isPatient,
  });

  const queryError =
    systemQuery.error ||
    patientReportQuery.error ||
    financialQuery.error ||
    appointmentsQuery.error ||
    plansQuery.error ||
    invoicesQuery.error;

  const chartData = isAdmin
    ? (systemQuery.data?.daily ?? []).slice(-10).map((item) => ({
        label: item.date.slice(5),
        value: item.appointments,
      }))
    : isStaff
      ? (patientReportQuery.data?.daily ?? []).slice(-10).map((item) => ({
          label: item.date.slice(5),
          value: item.visits,
        }))
      : [
          {
            label: 'Booked',
            value: (appointmentsQuery.data ?? []).filter((a) => a.status === 'booked').length,
          },
          {
            label: 'Completed',
            value: (appointmentsQuery.data ?? []).filter((a) => a.status === 'completed').length,
          },
          {
            label: 'Cancelled',
            value: (appointmentsQuery.data ?? []).filter((a) => a.status === 'cancelled').length,
          },
        ];

  const unpaidBalance = (invoicesQuery.data ?? []).reduce((sum, inv) => {
    if (inv.status === 'cancelled' || inv.status === 'paid') return sum;
    return sum + toAmount(inv.balance ?? inv.total_amount);
  }, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">System Overview & Analytics</h1>
          <p className="text-sm text-slate-500">
            Live operational metrics, patient volume, and orthopedic clinical performance
          </p>
        </div>

        {(isAdmin || isStaff) && (
          <div className="flex items-center gap-2 bg-white p-2.5 rounded-xl border border-slate-200 text-xs">
            <label htmlFor="report-start" className="text-slate-600 font-medium">
              From
            </label>
            <input
              id="report-start"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="border border-slate-300 rounded px-2 py-1"
            />
            <label htmlFor="report-end" className="text-slate-600 font-medium">
              To
            </label>
            <input
              id="report-end"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="border border-slate-300 rounded px-2 py-1"
            />
          </div>
        )}
      </div>

      {queryError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{extractApiError(queryError, 'Unable to load dashboard analytics.')}</span>
        </div>
      )}

      {isAdmin && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Patients Seen</span>
              <Users className="w-4 h-4 text-blue-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {patientReportQuery.data?.totals.patients ?? 0}
            </p>
            <span className="text-xs text-slate-500">
              {patientReportQuery.data?.totals.visits ?? 0} clinical encounters
            </span>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Appointments</span>
              <CalendarCheck className="w-4 h-4 text-teal-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {systemQuery.data?.totals.appointments ?? 0}
            </p>
            <span className="text-xs text-slate-500">
              {systemQuery.data?.appointments_by_status.completed ?? 0} completed •{' '}
              {systemQuery.data?.totals.logins ?? 0} logins
            </span>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Collected Revenue</span>
              <DollarSign className="w-4 h-4 text-emerald-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {formatCurrency(financialQuery.data?.totals.revenue ?? 0)}
            </p>
            <span className="text-xs text-emerald-600 font-medium">Settled payments (EGP)</span>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Outstanding Balance</span>
              <Activity className="w-4 h-4 text-amber-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {formatCurrency(financialQuery.data?.totals.outstanding ?? 0)}
            </p>
            <span className="text-xs text-slate-500">
              {financialQuery.data?.totals.open_invoices ?? 0} open invoices
            </span>
          </div>
        </div>
      )}

      {isStaff && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Patients Seen</span>
              <Users className="w-4 h-4 text-blue-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {patientReportQuery.data?.totals.patients ?? 0}
            </p>
            <span className="text-xs text-slate-500">
              {patientReportQuery.data?.totals.visits ?? 0} recorded visits
            </span>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Booked Appointments</span>
              <CalendarCheck className="w-4 h-4 text-teal-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {(appointmentsQuery.data ?? []).filter((a) => a.status === 'booked').length}
            </p>
            <span className="text-xs text-slate-500">
              {(appointmentsQuery.data ?? []).length} total in schedule
            </span>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Active Rehab Plans</span>
              <Activity className="w-4 h-4 text-indigo-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {(plansQuery.data ?? []).filter((p) => p.status === 'active').length}
            </p>
            <span className="text-xs text-slate-500">Ongoing physiotherapy</span>
          </div>
        </div>
      )}

      {isPatient && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Upcoming Appointments</span>
              <CalendarCheck className="w-4 h-4 text-teal-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {(appointmentsQuery.data ?? []).filter((a) => a.status === 'booked').length}
            </p>
            <span className="text-xs text-slate-500">Scheduled visits</span>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Active Rehab Plans</span>
              <Activity className="w-4 h-4 text-indigo-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">
              {(plansQuery.data ?? []).filter((p) => p.status === 'active').length}
            </p>
            <span className="text-xs text-slate-500">Assigned recovery plans</span>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Balance Due</span>
              <DollarSign className="w-4 h-4 text-emerald-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">{formatCurrency(unpaidBalance)}</p>
            <span className="text-xs text-slate-500">
              {(invoicesQuery.data ?? []).filter((i) => i.status !== 'paid').length} open invoices
            </span>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-base font-semibold text-slate-900 mb-4">
            {isAdmin
              ? 'Daily Appointments Activity'
              : isStaff
                ? 'Daily Clinical Visits'
                : 'My Appointment Breakdown'}
          </h2>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#2563eb" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {(isAdmin || isStaff) && (
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-3">
            <h2 className="text-base font-semibold text-slate-900">Top ICD-10 Diagnoses</h2>
            {(patientReportQuery.data?.diagnoses ?? []).length === 0 ? (
              <p className="text-xs text-slate-500">No coded diagnoses recorded in this period.</p>
            ) : (
              <div className="divide-y divide-slate-100 text-sm">
                {(patientReportQuery.data?.diagnoses ?? []).map((diag) => (
                  <div key={diag.code} className="py-2.5 flex items-center justify-between gap-2">
                    <div>
                      <span className="font-mono text-xs font-semibold text-indigo-600">
                        {diag.code}
                      </span>
                      <p className="text-xs text-slate-600">{diag.description}</p>
                    </div>
                    <span className="text-xs font-semibold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                      {diag.visits}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
