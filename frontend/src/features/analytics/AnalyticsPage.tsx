import React from 'react';
import { Users, CalendarCheck, DollarSign, Activity } from 'lucide-react';
import { usePermissions } from '../../hooks/usePermissions';
import { formatCurrency } from '../../utils/formatters';

const MONTHLY_STATS = [
  { month: 'Jun', patients: 320, revenue: 42000 },
  { month: 'Jul', patients: 390, revenue: 51500 },
  { month: 'Aug', patients: 410, revenue: 54800 },
  { month: 'Sep', patients: 465, revenue: 61200 },
  { month: 'Oct', patients: 510, revenue: 68900 },
  { month: 'Nov', patients: 548, revenue: 74300 },
];

export const AnalyticsPage: React.FC = () => {
  const { isAdmin, isClinical } = usePermissions();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">System Overview & Analytics</h1>
        <p className="text-sm text-slate-500">
          Real-time operational metrics, patient volume, and clinical performance
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium uppercase">Total Patients</span>
            <Users className="w-4 h-4 text-blue-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900">2,643</p>
          <span className="text-xs text-emerald-600 font-medium">+12.4% from last month</span>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium uppercase">Today's Appointments</span>
            <CalendarCheck className="w-4 h-4 text-teal-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900">48</p>
          <span className="text-xs text-slate-500">92% attendance rate</span>
        </div>

        {(isAdmin || isClinical) && (
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">CDSS Scans Analyzed</span>
              <Activity className="w-4 h-4 text-indigo-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">184</p>
            <span className="text-xs text-indigo-600 font-medium">Avg turnaround: 1.8s</span>
          </div>
        )}

        {isAdmin && (
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-2">
              <span className="text-xs font-medium uppercase">Monthly Revenue</span>
              <DollarSign className="w-4 h-4 text-emerald-600" />
            </div>
            <p className="text-2xl font-bold text-slate-900">{formatCurrency(74300)}</p>
            <span className="text-xs text-emerald-600 font-medium">+7.8% vs target</span>
          </div>
        )}
      </div>

      {/* Visual Bar Chart */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
        <h2 className="text-base font-semibold text-slate-900 mb-4">
          6-Month Patient Visits & Department Load
        </h2>
        <div className="grid grid-cols-6 gap-4 items-end h-52 pt-6 px-2 border-b border-slate-100">
          {MONTHLY_STATS.map((item) => {
            const heightPercent = Math.round((item.patients / 600) * 100);
            return (
              <div key={item.month} className="flex flex-col items-center gap-2 h-full justify-end">
                <span className="text-xs font-semibold text-slate-700">{item.patients}</span>
                <div
                  style={{ height: `${heightPercent}%` }}
                  className="w-full max-w-12 bg-blue-600 rounded-t-lg transition-all hover:bg-blue-700"
                />
                <span className="text-xs text-slate-500 font-medium">{item.month}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};