/**
 * @jest-environment jsdom
 */
import '@testing-library/jest-dom';
import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App.jsx';

function fhirResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

function searchBundle(resources) {
  return fhirResponse({
    resourceType: 'Bundle',
    type: 'searchset',
    total: resources.length,
    entry: resources.map((resource) => ({ resource })),
    link: [],
  });
}

describe('EMR Client React UI & HL7 FHIR R4 Workspace', () => {
  beforeEach(() => {
    globalThis.fetch = jest.fn();
  });

  afterEach(() => {
    cleanup();
    delete globalThis.fetch;
  });

  test('connects with a patient token (gracefully handling 403 on metadata) and navigates all 5 FHIR tabs', async () => {
    globalThis.fetch.mockImplementation(async (input) => {
      const href = String(input);
      if (href.includes('/fhir/metadata')) {
        return fhirResponse(
          {
            resourceType: 'OperationOutcome',
            issue: [{ diagnostics: 'Forbidden for patient role.' }],
          },
          403,
        );
      }
      if (href.includes('/fhir/Patient?')) {
        return searchBundle([
          {
            resourceType: 'Patient',
            id: '1',
            name: [{ text: 'Omar Hassan' }],
            birthDate: '1992-04-12',
          },
        ]);
      }
      if (href.includes('/fhir/Appointment?')) {
        return searchBundle([
          {
            resourceType: 'Appointment',
            id: '10',
            appointmentType: { text: 'consultation' },
            start: '2026-11-27T10:00:00Z',
            end: '2026-11-27T10:30:00Z',
            status: 'booked',
          },
        ]);
      }
      if (href.includes('/fhir/Encounter?')) {
        return searchBundle([
          {
            resourceType: 'Encounter',
            id: '7',
            period: { start: '2026-11-20' },
            reasonCode: [{ text: 'Medial knee pain' }],
          },
        ]);
      }
      if (href.includes('/fhir/Condition?')) {
        return searchBundle([
          {
            resourceType: 'Condition',
            id: '7',
            encounter: { reference: 'Encounter/7' },
            code: {
              text: 'Osteoarthritis of knee',
              coding: [{ code: 'M17.9' }],
            },
          },
        ]);
      }
      if (href.includes('/fhir/MedicationRequest?')) {
        return searchBundle([
          {
            resourceType: 'MedicationRequest',
            id: '4',
            encounter: { reference: 'Encounter/7' },
            medicationCodeableConcept: { text: 'Celecoxib 200 mg' },
            dosageInstruction: [{ text: 'Once daily for 14 days' }],
          },
        ]);
      }
      if (href.includes('/fhir/CarePlan?')) {
        return searchBundle([
          {
            resourceType: 'CarePlan',
            id: '3',
            title: 'ACL Strengthening Plan',
            description: 'Restore 130 deg flexion',
            period: { start: '2026-11-01' },
            status: 'active',
          },
        ]);
      }
      if (href.includes('/fhir/Procedure?')) {
        return searchBundle([
          {
            resourceType: 'Procedure',
            id: '9',
            performedDateTime: '2026-11-22',
            note: [{ text: 'Quad sets and bike' }],
          },
        ]);
      }
      if (href.includes('/fhir/Observation?')) {
        return searchBundle([
          {
            resourceType: 'Observation',
            id: '9-pain',
            partOf: [{ reference: 'Procedure/9' }],
            code: { text: 'Pain score' },
            valueQuantity: { value: 2, unit: 'score' },
          },
          {
            resourceType: 'Observation',
            id: '9-rom',
            partOf: [{ reference: 'Procedure/9' }],
            code: { text: 'Range of motion' },
            valueQuantity: { value: 118, unit: 'deg' },
          },
        ]);
      }
      if (href.includes('/fhir/ImagingStudy?')) {
        return searchBundle([
          {
            resourceType: 'ImagingStudy',
            id: '5',
            identifier: [{ system: 'urn:dicom:uid', value: 'urn:oid:2.25.3200021' }],
            started: '2026-11-18',
            modality: [{ code: 'DX' }],
            description: 'Right Knee',
          },
        ]);
      }
      if (href.includes('/fhir/DiagnosticReport?')) {
        return searchBundle([
          {
            resourceType: 'DiagnosticReport',
            id: '12',
            imagingStudy: [{ reference: 'ImagingStudy/5' }],
            status: 'final',
            conclusion: 'Joint space preserved, no acute fracture.',
          },
        ]);
      }
      return searchBundle([]);
    });

    render(<App />);

    await userEvent.type(screen.getByLabelText(/Access token/i), 'patient-demo-jwt');
    await userEvent.click(screen.getByRole('button', { name: /Connect/i }));

    // Appointments tab (default)
    expect(await screen.findByText('Omar Hassan')).toBeInTheDocument();
    expect(await screen.findByText('consultation')).toBeInTheDocument();
    expect(screen.getByText('2026-11-27 10:00 UTC')).toBeInTheDocument();

    // Visit history tab (joins Encounter + Condition)
    await userEvent.click(screen.getByRole('button', { name: /Visit history/i }));
    expect(await screen.findByText('Osteoarthritis of knee')).toBeInTheDocument();
    expect(screen.getByText('M17.9')).toBeInTheDocument();

    // Prescriptions tab
    await userEvent.click(screen.getByRole('button', { name: /Prescriptions/i }));
    expect(await screen.findByText('Celecoxib 200 mg')).toBeInTheDocument();
    expect(screen.getByText('Once daily for 14 days')).toBeInTheDocument();

    // Rehabilitation tab (joins CarePlan + Procedure + Observation)
    await userEvent.click(screen.getByRole('button', { name: /Rehabilitation/i }));
    expect(await screen.findByText('ACL Strengthening Plan')).toBeInTheDocument();
    expect(screen.getByText(/Pain score: 2 score · Range of motion: 118 deg/)).toBeInTheDocument();

    // Imaging tab (strips urn:oid: and maps status 'final' -> 'Final')
    await userEvent.click(screen.getByRole('button', { name: /Imaging/i }));
    expect(await screen.findByText('2.25.3200021')).toBeInTheDocument();
    expect(screen.getByText('Final')).toBeInTheDocument();
    expect(screen.getByText('Joint space preserved, no acute fracture.')).toBeInTheDocument();

    // Sign out returns to token prompt
    await userEvent.click(screen.getByRole('button', { name: /Sign out/i }));
    expect(screen.getByRole('button', { name: /Connect/i })).toBeInTheDocument();
  });

  test('resets session and shows alert when FHIR server returns 401 OperationOutcome', async () => {
    globalThis.fetch.mockResolvedValue(
      fhirResponse(
        {
          resourceType: 'OperationOutcome',
          issue: [{ diagnostics: 'Token expired.' }],
        },
        401,
      ),
    );

    render(<App />);
    await userEvent.type(screen.getByLabelText(/Access token/i), 'expired-token');
    await userEvent.click(screen.getByRole('button', { name: /Connect/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid or expired/i);
    });
  });
});
