import { afterEach, beforeEach, expect, jest, test } from '@jest/globals';
import { fhirGet, fhirList } from '../src/services/fhir.mjs';

const origin = 'http://localhost:5174';
const path = '/api/v1/fhir/DiagnosticReport';
const token = 'test-token';
const filters = { patient: 'Patient/7' };
const firstPage = `${origin}${path}?_count=100&patient=Patient%2F7`;

function reply(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status });
}

function bundle(ids, next) {
  return {
    resourceType: 'Bundle',
    type: 'searchset',
    entry: ids.map((id) => ({ resource: { resourceType: 'DiagnosticReport', id } })),
    link: next ? [{ relation: 'next', url: next }] : [],
  };
}

beforeEach(() => {
  globalThis.window = { location: { origin } };
  jest.spyOn(globalThis, 'fetch');
});

afterEach(() => {
  jest.restoreAllMocks();
  delete globalThis.window;
});

test('follows FHIR pagination with the selected patient and the access token', async () => {
  const next = `${firstPage}&_page=2`;
  fetch
    .mockResolvedValueOnce(reply(bundle(['1'], next)))
    .mockResolvedValueOnce(reply(bundle(['2'])));
  const values = await fhirList('DiagnosticReport', token, filters);
  expect(values.map(({ id }) => id)).toEqual(['1', '2']);
  expect(fetch.mock.calls.map(([url]) => url.href)).toEqual([firstPage, next]);
  for (const [, options] of fetch.mock.calls) {
    expect(options.redirect).toBe('error');
    expect(options.headers).toEqual({
      Accept: 'application/fhir+json',
      Authorization: 'Bearer test-token',
    });
  }
});

test.each([
  `https://example.invalid${path}?patient=Patient%2F7`,
  `${origin}/api/v1/fhir/Patient?patient=Patient%2F7`,
  `${origin}${path}?patient=Patient%2F8`,
  firstPage,
])('stops unsafe or repeating pagination at %s', async (next) => {
  fetch.mockResolvedValueOnce(reply(bundle([], next)));
  await expect(fhirList('DiagnosticReport', token, filters)).rejects.toThrow(/search link/);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('preserves the HTTP status and FHIR authentication diagnostic', async () => {
  fetch.mockResolvedValueOnce(
    reply(
      {
        resourceType: 'OperationOutcome',
        issue: [{ diagnostics: 'Expired.' }],
      },
      401,
    ),
  );
  await expect(fhirGet('metadata', token)).rejects.toMatchObject({
    status: 401,
    message: 'Expired.',
  });
});
