import { formatCurrency, formatDate, formatDateTime, toAmount } from '../utils/formatters';

describe('formatters utility', () => {
  it('parses numbers and backend Decimal strings safely in toAmount', () => {
    expect(toAmount(300)).toBe(300);
    expect(toAmount('500.25')).toBe(500.25);
    expect(toAmount(null)).toBe(0);
    expect(toAmount('not-a-number')).toBe(0);
  });

  it('formats EGP currency for both numbers and Decimal strings', () => {
    expect(formatCurrency('300.00')).toContain('EGP');
    expect(formatCurrency('300.00')).toContain('300.00');
    expect(formatCurrency(1250.5)).toContain('1,250.50');
  });

  it('formats ISO date-only strings without timezone drift', () => {
    expect(formatDate('2026-11-25')).toBe('Nov 25, 2026');
    expect(formatDate('')).toBe('—');
  });

  it('formats full ISO date-time strings and handles empty values', () => {
    expect(formatDateTime('2026-11-25T10:30:00Z')).toContain('Nov');
    expect(formatDateTime('')).toBe('—');
  });
});
