export const toAmount = (amount: number | string | null | undefined): number => {
  if (typeof amount === 'number') {
    return Number.isFinite(amount) ? amount : 0;
  }
  if (typeof amount === 'string') {
    const parsed = Number(amount);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

export const formatCurrency = (amount: number | string | null | undefined): string => {
  const numeric = toAmount(amount);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'EGP',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);
};

export const formatDate = (isoString: string): string => {
  if (!isoString) return '—';
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(isoString);
  const parsed = new Date(dateOnly ? `${isoString}T00:00:00Z` : isoString);
  if (Number.isNaN(parsed.getTime())) return isoString;
  return parsed.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...(dateOnly ? { timeZone: 'UTC' } : {}),
  });
};

export const formatDateTime = (isoString: string): string => {
  if (!isoString) return '—';
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return isoString;
  return parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};
