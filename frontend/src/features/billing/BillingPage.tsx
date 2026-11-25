import React, { useState } from 'react';
import { Plus, CreditCard, CheckCircle } from 'lucide-react';
import type { Invoice } from '../../types';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { usePermissions } from '../../hooks/usePermissions';

const ICD10_CATALOG = [
  { code: 'M23.51', desc: 'Chronic instability of knee, right knee' },
  { code: 'S83.511A', desc: 'Sprain of anterior cruciate ligament of right knee' },
  { code: 'M54.50', desc: 'Low back pain, unspecified' },
  { code: 'M17.11', desc: 'Unilateral primary osteoarthritis, right knee' },
  { code: 'Z47.89', desc: 'Encounter for other orthopedic aftercare' },
];

export const BillingPage: React.FC = () => {
  const { isAdmin, isStaff } = usePermissions();
  const [invoices, setInvoices] = useState<Invoice[]>([
    {
      invoice_id: 2026089,
      patient_id: 101,
      patient_name: 'Omar Hassan',
      icd10_code: 'S83.511A',
      issue_date: '2026-11-21T10:00:00Z',
      due_date: '2026-12-05T10:00:00Z',
      items: [
        {
          item_id: 1,
          invoice_id: 2026089,
          service_id: 12,
          service_name: 'Knee MRI Scan + AI Orthopedic CDSS Report',
          quantity: 1,
          unit_price: 320,
        },
      ],
      total_amount: 320,
      status: 'unpaid',
    },
  ]);

  const [selectedIcd, setSelectedIcd] = useState(ICD10_CATALOG[0].code);
  const [serviceDesc, setServiceDesc] = useState('');
  const [amount, setAmount] = useState('');

  const handleCreateInvoice = (e: React.FormEvent) => {
    e.preventDefault();
    const price = parseFloat(amount) || 0;
    const invoiceId = Math.floor(100000 + Math.random() * 900000);
    const newInv: Invoice = {
      invoice_id: invoiceId,
      patient_id: 101,
      patient_name: 'Omar Hassan',
      icd10_code: selectedIcd,
      issue_date: new Date().toISOString(),
      due_date: new Date(Date.now() + 14 * 86400000).toISOString(),
      items: [
        {
          item_id: Date.now(),
          invoice_id: invoiceId,
          service_id: 15,
          service_name: serviceDesc,
          quantity: 1,
          unit_price: price,
        },
      ],
      total_amount: price,
      status: 'unpaid',
    };
    setInvoices([newInv, ...invoices]);
    setServiceDesc('');
    setAmount('');
  };

  const markAsPaid = (id: number) => {
    setInvoices((prev) =>
      prev.map((inv) => (inv.invoice_id === id ? { ...inv, status: 'paid' } : inv)),
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Billing, Invoicing & ICD-10 Coding</h1>
        <p className="text-sm text-slate-500">
          Standardized orthopedic billing linked with ICD-10 diagnostic codes
        </p>
      </div>

      {(isAdmin || isStaff) && (
        <form
          onSubmit={handleCreateInvoice}
          className="bg-white p-5 rounded-xl border border-slate-200 grid sm:grid-cols-4 gap-3 items-end"
        >
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              ICD-10 Diagnosis Code
            </label>
            <select
              value={selectedIcd}
              onChange={(e) => setSelectedIcd(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            >
              {ICD10_CATALOG.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.code} — {c.desc}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Service Description
            </label>
            <input
              required
              placeholder="e.g., Physiotherapy Session"
              value={serviceDesc}
              onChange={(e) => setServiceDesc(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Amount (USD)</label>
            <input
              type="number"
              required
              min="1"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <button
            type="submit"
            className="flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Generate Invoice
          </button>
        </form>
      )}

      <div className="space-y-4">
        {invoices.map((inv) => {
          const icdMatch = ICD10_CATALOG.find((c) => c.code === inv.icd10_code);
          return (
            <div
              key={inv.invoice_id}
              className="bg-white p-5 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <span className="font-bold text-slate-900">INV-{inv.invoice_id}</span>
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase ${
                      inv.status === 'paid'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-amber-50 text-amber-700'
                    }`}
                  >
                    {inv.status}
                  </span>
                </div>
                <p className="text-sm text-slate-700">{inv.items?.[0]?.service_name}</p>
                <p className="text-xs text-slate-500">
                  ICD-10:{' '}
                  <span className="font-mono font-semibold text-indigo-600">{inv.icd10_code}</span>{' '}
                  {icdMatch ? `(${icdMatch.desc})` : ''} • Issued {formatDate(inv.issue_date)}
                </p>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-xs text-slate-400">Total Amount</p>
                  <p className="text-lg font-bold text-slate-900">
                    {formatCurrency(inv.total_amount)}
                  </p>
                </div>
                {inv.status !== 'paid' ? (
                  <button
                    onClick={() => markAsPaid(inv.invoice_id)}
                    className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                  >
                    <CreditCard className="w-4 h-4" />
                    Pay Now
                  </button>
                ) : (
                  <span className="flex items-center gap-1 text-xs font-semibold text-emerald-600">
                    <CheckCircle className="w-4 h-4" />
                    Settled
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
