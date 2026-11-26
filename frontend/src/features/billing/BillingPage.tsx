import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, CreditCard, CheckCircle, AlertCircle, Tag } from 'lucide-react';
import { extractApiError } from '../../api/client';
import { billingApi, usersApi } from '../../api/endpoints';
import { usePermissions } from '../../hooks/usePermissions';
import type { Invoice } from '../../types';
import { formatCurrency, formatDate, toAmount } from '../../utils/formatters';

function defaultDueDate(): string {
  return new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
}

export const BillingPage: React.FC = () => {
  const { isAdmin, isStaff, isPatient } = usePermissions();
  const queryClient = useQueryClient();

  // Invoice creation form
  const [patientId, setPatientId] = useState<number | ''>('');
  const [serviceId, setServiceId] = useState<number | ''>('');
  const [quantity, setQuantity] = useState(1);
  const [icdQuery, setIcdQuery] = useState('');
  const [selectedIcd, setSelectedIcd] = useState('');
  const [dueDate, setDueDate] = useState(defaultDueDate());

  // Admin service catalogue form
  const [newServiceName, setNewServiceName] = useState('');
  const [newServicePrice, setNewServicePrice] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<'online' | 'cash' | 'card'>('online');
  const [actionError, setActionError] = useState<string | null>(null);

  const servicesQuery = useQuery({
    queryKey: ['services', isAdmin],
    queryFn: async () => (await billingApi.listServices(isAdmin)).data,
  });

  const invoicesQuery = useQuery({
    queryKey: ['invoices'],
    queryFn: async () => (await billingApi.listInvoices()).data,
  });

  const patientsQuery = useQuery({
    queryKey: ['patients'],
    queryFn: async () => (await usersApi.listPatients()).data,
    enabled: isAdmin || isStaff,
  });

  const icdSearchQuery = useQuery({
    queryKey: ['icd10', icdQuery],
    queryFn: async () => (await billingApi.searchIcd10(icdQuery)).data,
    enabled: isAdmin || isStaff,
  });

  const createInvoiceMutation = useMutation({
    mutationFn: (payload: Parameters<typeof billingApi.createInvoice>[0]) =>
      billingApi.createInvoice(payload),
    onSuccess: () => {
      setActionError(null);
      setQuantity(1);
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to generate invoice.')),
  });

  const saveServiceMutation = useMutation({
    mutationFn: (payload: Parameters<typeof billingApi.saveService>[0]) =>
      billingApi.saveService(payload),
    onSuccess: () => {
      setActionError(null);
      setNewServiceName('');
      setNewServicePrice('');
      queryClient.invalidateQueries({ queryKey: ['services'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Failed to save service item.')),
  });

  const payMutation = useMutation({
    mutationFn: ({ invoice, method }: { invoice: Invoice; method: 'online' | 'cash' | 'card' }) => {
      const payable = toAmount(invoice.balance ?? invoice.total_amount).toFixed(2);
      return billingApi.payInvoice(invoice.invoice_id, {
        amount: payable,
        method: isPatient ? 'online' : method,
      });
    },
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
    onError: (err) => setActionError(extractApiError(err, 'Payment processing failed.')),
  });

  const activeServices = (servicesQuery.data ?? []).filter((s) => s.is_active);
  const effectivePatientId =
    patientId !== '' ? patientId : (patientsQuery.data?.[0]?.patient_id ?? '');
  const effectiveServiceId = serviceId !== '' ? serviceId : (activeServices[0]?.service_id ?? '');
  const icdOptions = icdSearchQuery.data ?? [];
  const effectiveIcd = selectedIcd || icdOptions[0]?.code || '';

  const handleCreateInvoice = (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectivePatientId || !effectiveServiceId) {
      setActionError('Select a patient and an active billable service.');
      return;
    }
    createInvoiceMutation.mutate({
      patient_id: Number(effectivePatientId),
      due_date: dueDate,
      icd10_code: effectiveIcd || undefined,
      items: [{ service_id: Number(effectiveServiceId), quantity }],
    });
  };

  const handleAddService = (e: React.FormEvent) => {
    e.preventDefault();
    saveServiceMutation.mutate({
      name: newServiceName.trim(),
      price: Number(newServicePrice).toFixed(2),
      is_active: true,
    });
  };

  const invoices = invoicesQuery.data ?? [];
  const patientMap = new Map((patientsQuery.data ?? []).map((p) => [p.patient_id, p.full_name]));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Billing, Invoicing & ICD-10 Coding</h1>
          <p className="text-sm text-slate-500">
            Standardized orthopedic billing (EGP) linked with WHO ICD-10 diagnostic codes
          </p>
        </div>

        {isAdmin && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-600 font-medium">Admin Payment Method:</span>
            <select
              aria-label="Payment method"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as 'online' | 'cash' | 'card')}
              className="border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white"
            >
              <option value="online">Online</option>
              <option value="cash">Cash</option>
              <option value="card">Card</option>
            </select>
          </div>
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

      {isAdmin && (
        <form
          onSubmit={handleAddService}
          className="bg-white p-4 rounded-xl border border-slate-200 flex flex-wrap items-end gap-3"
        >
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="svc-name" className="block text-xs font-medium text-slate-700 mb-1">
              Add Service to Price Catalogue
            </label>
            <input
              id="svc-name"
              required
              placeholder="e.g., Arthroscopic Follow-up"
              value={newServiceName}
              onChange={(e) => setNewServiceName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <div className="w-40">
            <label htmlFor="svc-price" className="block text-xs font-medium text-slate-700 mb-1">
              Unit Price (EGP)
            </label>
            <input
              id="svc-price"
              type="number"
              step="0.01"
              min="1"
              required
              placeholder="350.00"
              value={newServicePrice}
              onChange={(e) => setNewServicePrice(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={saveServiceMutation.isPending}
            className="flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white py-2 px-4 rounded-lg text-sm font-medium"
          >
            <Tag className="w-4 h-4" />
            Save Service
          </button>
        </form>
      )}

      {(isAdmin || isStaff) && (
        <form
          onSubmit={handleCreateInvoice}
          className="bg-white p-5 rounded-xl border border-slate-200 grid sm:grid-cols-6 gap-3 items-end"
        >
          <div>
            <label htmlFor="inv-patient" className="block text-xs font-medium text-slate-700 mb-1">
              Patient
            </label>
            <select
              id="inv-patient"
              value={effectivePatientId}
              onChange={(e) => setPatientId(Number(e.target.value))}
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
            <label htmlFor="inv-service" className="block text-xs font-medium text-slate-700 mb-1">
              Service Item
            </label>
            <select
              id="inv-service"
              value={effectiveServiceId}
              onChange={(e) => setServiceId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
            >
              {activeServices.map((s) => (
                <option key={s.service_id} value={s.service_id}>
                  {s.name} ({formatCurrency(s.price)})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="inv-qty" className="block text-xs font-medium text-slate-700 mb-1">
              Quantity
            </label>
            <input
              id="inv-qty"
              type="number"
              min={1}
              max={100}
              required
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>

          <div>
            <label htmlFor="inv-icd-q" className="block text-xs font-medium text-slate-700 mb-1">
              Filter ICD-10
            </label>
            <input
              id="inv-icd-q"
              placeholder="Search code/title"
              value={icdQuery}
              onChange={(e) => {
                setIcdQuery(e.target.value);
                setSelectedIcd('');
              }}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>

          <div>
            <label htmlFor="inv-icd" className="block text-xs font-medium text-slate-700 mb-1">
              ICD-10 Code
            </label>
            <select
              id="inv-icd"
              value={effectiveIcd}
              onChange={(e) => setSelectedIcd(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
            >
              <option value="">None</option>
              {icdOptions.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.code} — {c.description}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <input
              aria-label="Due date"
              type="date"
              required
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs"
            />
            <button
              type="submit"
              disabled={createInvoiceMutation.isPending || activeServices.length === 0}
              className="w-full flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2 px-3 rounded-lg text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              Generate Invoice
            </button>
          </div>
        </form>
      )}

      <div className="space-y-4">
        {invoicesQuery.isLoading ? (
          <div className="bg-white p-6 rounded-xl border border-slate-200 text-sm text-slate-500">
            Loading invoices...
          </div>
        ) : invoices.length === 0 ? (
          <div className="bg-white p-6 rounded-xl border border-slate-200 text-sm text-slate-500">
            No invoices found.
          </div>
        ) : (
          invoices.map((inv) => {
            const canPay =
              (isPatient || isAdmin) && inv.status !== 'paid' && inv.status !== 'cancelled';
            const balanceDue = toAmount(inv.balance ?? inv.total_amount);
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
                          : inv.status === 'partial'
                            ? 'bg-blue-50 text-blue-700'
                            : 'bg-amber-50 text-amber-700'
                      }`}
                    >
                      {inv.status}
                    </span>
                    <span className="text-xs text-slate-500">
                      {patientMap.get(inv.patient_id) || `Patient #${inv.patient_id}`}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    {inv.icd10_code && (
                      <>
                        ICD-10:{' '}
                        <span className="font-mono font-semibold text-indigo-600">
                          {inv.icd10_code}
                        </span>{' '}
                        •{' '}
                      </>
                    )}
                    Issued {formatDate(inv.issue_date)} • Due {formatDate(inv.due_date)}
                  </p>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-xs text-slate-400">
                      {balanceDue > 0 && inv.status !== 'paid' ? 'Balance Due' : 'Total Amount'}
                    </p>
                    <p className="text-lg font-bold text-slate-900">
                      {formatCurrency(
                        inv.status === 'paid'
                          ? inv.total_amount
                          : (inv.balance ?? inv.total_amount),
                      )}
                    </p>
                  </div>
                  {canPay ? (
                    <button
                      type="button"
                      disabled={payMutation.isPending}
                      onClick={() => payMutation.mutate({ invoice: inv, method: paymentMethod })}
                      className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                    >
                      <CreditCard className="w-4 h-4" />
                      Pay Now
                    </button>
                  ) : inv.status === 'paid' ? (
                    <span className="flex items-center gap-1 text-xs font-semibold text-emerald-600">
                      <CheckCircle className="w-4 h-4" />
                      Settled
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
