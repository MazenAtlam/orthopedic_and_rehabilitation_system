import { useEffect, useState } from 'react';
import { fhirList } from '../services/fhir.mjs';

const tabs = {
  Appointments: ['Appointment'],
  'Visit history': ['Encounter', 'Condition'],
  Prescriptions: ['MedicationRequest'],
  Rehabilitation: ['CarePlan', 'Procedure', 'Observation'],
  Imaging: ['ImagingStudy', 'DiagnosticReport'],
};

function patientName(patient) {
  const name = patient.name?.[0];
  return (
    name?.text ||
    [...(name?.given ?? []), name?.family].filter(Boolean).join(' ') ||
    `Patient #${patient.id}`
  );
}

export default function PatientRecords({ patients, available, token, onExpired }) {
  const [id, setId] = useState(patients[0].id);
  const [tab, setTab] = useState('Appointments');
  const patient = patients.find((item) => item.id === id);
  const visible = Object.keys(tabs).filter(
    (name) => !available || tabs[name].every((kind) => available.includes(kind)),
  );
  const selected = visible.includes(tab) ? tab : visible[0];

  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>{patientName(patient)}</h2>
          <p className="context">
            Patient #{id}
            {patient.birthDate && ` · Born ${patient.birthDate}`}
          </p>
        </div>
        {patients.length > 1 && (
          <div>
            <label htmlFor="patient-select">Patient</label>
            <select id="patient-select" value={id} onChange={(event) => setId(event.target.value)}>
              {patients.map((item) => (
                <option key={item.id} value={item.id}>
                  {patientName(item)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {selected ? (
        <>
          <nav aria-label="Patient record sections">
            {visible.map((name) => (
              <button
                type="button"
                aria-pressed={selected === name}
                key={name}
                onClick={() => setTab(name)}
              >
                {name}
              </button>
            ))}
          </nav>
          <RecordDetails
            key={`${id}-${selected}`}
            tab={selected}
            id={id}
            token={token}
            onExpired={onExpired}
          />
        </>
      ) : (
        <Empty>No record sections are available for this account.</Empty>
      )}
    </section>
  );
}

function RecordDetails({ id, tab, token, onExpired }) {
  const [result, setResult] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all(
      tabs[tab].map((kind) =>
        fhirList(kind, token, { patient: `Patient/${id}` }, controller.signal),
      ),
    )
      .then((data) => {
        if (!controller.signal.aborted) setResult({ data });
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        if (error.status === 401) onExpired();
        else setResult({ error: error.message });
      });
    return () => controller.abort();
  }, [id, tab, token, onExpired]);

  if (!result) return <p role="status">Loading {tab.toLowerCase()}…</p>;
  if (result.error) return <p role="alert">{result.error}</p>;
  const [first, second, third] = result.data;
  if (tab === 'Appointments') return <Appointments records={first} />;
  if (tab === 'Visit history') return <History records={first} diagnoses={second} />;
  if (tab === 'Prescriptions') return <Prescriptions records={first} />;
  if (tab === 'Imaging') return <Imaging studies={first} reports={second} />;
  return <Rehab plans={first} sessions={second} observations={third} />;
}

function Table({ headers, children }) {
  return (
    <div className="table-scroll" tabIndex={0}>
      <table>
        <thead>
          <tr>
            {headers.map((heading) => (
              <th key={heading} scope="col">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Status({ value }) {
  return <span className="status">{value ?? 'Unknown'}</span>;
}

function Empty({ children }) {
  return <p className="context">{children}</p>;
}

function formatTime(value) {
  return value ? `${value.slice(0, 10)} ${value.slice(11, 16)} UTC` : '—';
}

function Appointments({ records }) {
  return records.length ? (
    <Table headers={['Type', 'Starts', 'Ends', 'Status']}>
      {records.map((item) => (
        <tr key={item.id}>
          <td>{item.appointmentType?.text ?? '—'}</td>
          <td>{formatTime(item.start)}</td>
          <td>{formatTime(item.end)}</td>
          <td>
            <Status value={item.status} />
          </td>
        </tr>
      ))}
    </Table>
  ) : (
    <Empty>No appointments are recorded.</Empty>
  );
}

function History({ records, diagnoses }) {
  const index = new Map(diagnoses.map((item) => [item.encounter?.reference, item]));
  return records.length ? (
    <Table headers={['Visit date', 'Reason for visit', 'Diagnosis', 'ICD-10']}>
      {records.map((item) => {
        const diagnosis = index.get(`Encounter/${item.id}`);
        return (
          <tr key={item.id}>
            <td>{item.period?.start ?? '—'}</td>
            <td>{item.reasonCode?.[0]?.text ?? '—'}</td>
            <td>{diagnosis?.code?.text ?? '—'}</td>
            <td>{diagnosis?.code?.coding?.[0]?.code ?? '—'}</td>
          </tr>
        );
      })}
    </Table>
  ) : (
    <Empty>No visits are recorded.</Empty>
  );
}

function Prescriptions({ records }) {
  return records.length ? (
    <Table headers={['Medication', 'Recorded instructions', 'Visit']}>
      {records.map((item) => (
        <tr key={item.id}>
          <td>{item.medicationCodeableConcept?.text ?? '—'}</td>
          <td>{item.dosageInstruction?.[0]?.text ?? '—'}</td>
          <td>{item.encounter?.reference?.split('/')[1] ?? '—'}</td>
        </tr>
      ))}
    </Table>
  ) : (
    <Empty>No prescriptions are recorded.</Empty>
  );
}

function Rehab({ plans, sessions, observations }) {
  const measurements = new Map();
  for (const item of observations) {
    const ref = item.partOf?.[0]?.reference;
    const quantity = item.valueQuantity;
    if (ref && quantity) {
      const values = measurements.get(ref) ?? [];
      values.push(`${item.code.text}: ${quantity.value} ${quantity.unit}`);
      measurements.set(ref, values);
    }
  }
  return (
    <>
      <h3>Care plans</h3>
      {plans.length ? (
        <Table headers={['Plan', 'Goal', 'Start', 'Status']}>
          {plans.map((plan) => (
            <tr key={plan.id}>
              <td>{plan.title}</td>
              <td>{plan.description ?? '—'}</td>
              <td>{plan.period?.start ?? '—'}</td>
              <td>
                <Status value={plan.status} />
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <Empty>No care plans are recorded.</Empty>
      )}
      <h3 className="spaced">Sessions</h3>
      {sessions.length ? (
        <Table headers={['Session date', 'Notes', 'Measurements']}>
          {sessions.map((item) => (
            <tr key={item.id}>
              <td>{item.performedDateTime ?? '—'}</td>
              <td>{item.note?.map((note) => note.text).join(' · ') ?? '—'}</td>
              <td>{measurements.get(`Procedure/${item.id}`)?.join(' · ') ?? '—'}</td>
            </tr>
          ))}
        </Table>
      ) : (
        <Empty>No rehabilitation sessions are recorded.</Empty>
      )}
    </>
  );
}

const reportLabels = { final: 'Final', preliminary: 'Preliminary', 'entered-in-error': 'Rejected' };

function Imaging({ studies, reports }) {
  return (
    <>
      <h3>Imaging studies</h3>
      {studies.length ? (
        <Table headers={['FHIR study', 'DICOM Study UID', 'Study date', 'Modality', 'Body part']}>
          {studies.map((item) => {
            const uid = item.identifier?.find(
              (identifier) => identifier.system === 'urn:dicom:uid',
            )?.value;
            return (
              <tr key={item.id}>
                <td>ImagingStudy/{item.id}</td>
                <td>{uid?.replace(/^urn:oid:/, '') ?? '—'}</td>
                <td>{item.started?.slice(0, 10) ?? '—'}</td>
                <td>{item.modality?.map(({ code }) => code).join(', ') ?? '—'}</td>
                <td>{item.description ?? '—'}</td>
              </tr>
            );
          })}
        </Table>
      ) : (
        <Empty>No imaging studies are available.</Empty>
      )}
      <h3 className="spaced">Diagnostic reports</h3>
      {reports.length ? (
        <Table headers={['Study reference', 'Review status', 'Conclusion']}>
          {reports.map((report) => (
            <tr key={report.id}>
              <td>{report.imagingStudy?.map(({ reference }) => reference).join(', ') ?? '—'}</td>
              <td>{reportLabels[report.status] ?? report.status}</td>
              <td>{report.conclusion ?? '—'}</td>
            </tr>
          ))}
        </Table>
      ) : (
        <Empty>No diagnostic reports are available.</Empty>
      )}
    </>
  );
}
