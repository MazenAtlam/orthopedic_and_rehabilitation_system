import axios, { AxiosError, AxiosHeaders } from 'axios';
import { extractApiError } from '../api/client';

describe('extractApiError helper', () => {
  it('formats field-level validation details from backend 422 responses', () => {
    const err = new AxiosError('Unprocessable Entity', '422', undefined, undefined, {
      data: {
        error: {
          code: 'validation_failed',
          message: 'The request failed validation.',
          details: [
            { field: 'birth_date', message: 'Cannot be in the future.', code: 'invalid' },
            { field: 'phone', message: 'Invalid phone number.', code: 'invalid' },
          ],
        },
      },
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: {},
      config: { headers: new AxiosHeaders() },
    });

    expect(extractApiError(err)).toBe(
      'birth_date: Cannot be in the future. • phone: Invalid phone number.',
    );
  });

  it('extracts top-level backend error message when details are absent', () => {
    const err = new AxiosError('Conflict', '409', undefined, undefined, {
      data: {
        error: {
          code: 'appointment_conflict',
          message: 'The clinician already has an appointment in this slot.',
        },
      },
      status: 409,
      statusText: 'Conflict',
      headers: {},
      config: { headers: new AxiosHeaders() },
    });

    expect(extractApiError(err)).toBe('The clinician already has an appointment in this slot.');
  });

  it('falls back gracefully for non-Axios unknown values', () => {
    expect(axios.isAxiosError('plain-string')).toBe(false);
    expect(extractApiError(null, 'Custom fallback')).toBe('Custom fallback');
  });
});
