import React, { useState } from 'react';
import { Plus, CreditCard, CheckCircle } from 'lucide-react';
import { Invoice } from '../../types';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { usePermissions } from '../../hooks/usePermissions';

const ICD10_CATALOG = [
  { code: 'R05.9', desc: 'Cough, unspecified' },
  { code: 'I10', desc: 'Essential (primary) hypertension' },
  { code: 'J18.9', desc: 'Pneumonia, unspecified organism' },
  { code: 'G43.909', desc: 'Migraine, unspecified, not intractable' },
  { code: 'Z01.89', desc: 'Encounter for other specified special examinations (Radiology)' },
];

export const BillingPage: React.FC = () => {
  const { isAdmin } = usePermissions();
  const [invoices, setInvoices] = useState<Invoice[]>([
    {
      id: 'INV-2026-089',
      patientId: 'usr-pat-01',
      patientName: 'Omar Hassan',
      issuedAt: '2026-11-21T10:00:00Z',
      dueDate: '2026-12-05T10:00:00Z',
      items: [
        {
          id: 'item-1',
          description: 'Chest CT Scan + AI CDSS Diagnostic Report',
          icd10Code: 'R05.9',
          icd10Description: 'Cough, unspecified',
          quantity: 1,
          unitPrice: 320,
        },
      ],
      taxRate: 0.05,
      totalAmount: 336,
      status: 'PENDING',
    },
  ]);

  const [selectedIcd, setSelectedIcd] = useState(ICD10_CATALOG[0].code);
  const [serviceDesc, setServiceDesc] = useState('');
  const [amount, setAmount] = useState('');

  const handleCreateInvoice = (e: React.FormEvent) => {
    e.preventDefault();
    const icdObj = ICD10_CATALOG.find((c) => c.code === selectedIcd) || ICD10_CATALOG[0];
    const price = parseFloat(amount) || 0;
    const newInv: Invoice = {
      id: `INV-2026-${Math.floor(100 + Math.random() * 900)}`,
      patientId: 'usr-pat-01',
      patientName: 'Omar Hassan',
      issuedAt: new Date().toISOString(),
      dueDate: new Date(Date.now() + 14 * 86400000).toISOString(),
      items: [
        {
          id: `it-${Date.now()}`,
          description: serviceDesc,
          icd10Code: icdObj.code,
          icd10Description: icdObj.desc,
          quantity: 1,
          unitPrice: price,
        },
      ],
      taxRate: 0.05,
      totalAmount: price * 1.05,
      status: 'PENDING',
    };
    setInvoices([newInv, ...invoices]);
    setServiceDesc('');
    setAmount('');
  };

  const markAsPaid = (id: string) => {
    setInvoices((prev) => prev.map((inv) => (inv.id === id ? { ...inv, status: 'PAID' } : inv)));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Billing, Invoicing & ICD-10 Coding</h1>
        <p className="text-sm text-slate-500">
          Standardized medical billing linked with ICD-10 diagnostic codes
        </p>
      </div>

      {isAdmin && (
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
              placeholder="e.g., MRI Brain Scan"
              value={serviceDesc}
              onChange={(e) => setServiceDesc(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Base Amount (USD)
            </label>
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
        {invoices.map((inv) => (
          <div
            key={inv.id}
            className="bg-white p-5 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-4"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <span className="font-bold text-slate-900">{inv.id}</span>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                    inv.status === 'PAID'
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-amber-50 text-amber-700'
                  }`}
                >
                  {inv.status}
                </span>
              </div>
              <p className="text-sm text-slate-700">{inv.items[0]?.description}</p>
              <p className="text-xs text-slate-500">
                ICD-10:{' '}
                <span className="font-mono font-semibold text-indigo-600">
                  {inv.items[0]?.icd10Code}
                </span>{' '}
                ({inv.items[0]?.icd10Description}) • Issued {formatDate(inv.issuedAt)}
              </p>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-xs text-slate-400">Total (incl. 5% tax)</p>
                <p className="text-lg font-bold text-slate-900">
                  {formatCurrency(inv.totalAmount)}
                </p>
              </div>
              {inv.status === 'PENDING' ? (
                <button
                  onClick={() => markAsPaid(inv.id)}
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
        ))}
      </div>
    </div>
  );
};
