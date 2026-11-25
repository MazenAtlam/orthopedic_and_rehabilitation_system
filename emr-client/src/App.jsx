import { useCallback, useEffect, useState } from 'react';
import { fhirGet, fhirList } from './services/fhir.mjs';
import PatientRecords from './components/PatientRecords.jsx';
import './styles.css';

export default function App() {
  const [draft, setDraft] = useState('');
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');

  function start(event) {
    event.preventDefault();
    if (!draft.trim()) return;
    setToken(draft.trim());
    setDraft('');
    setMessage('');
  }

  const expire = useCallback(() => {
    setToken('');
    setMessage('Your access token is invalid or expired. Enter a new token to continue.');
  }, []);

  return (
    <main>
      <header>
        <div>
          <p className="context">Orthopedics & Rehabilitation · HL7 FHIR R4</p>
          <h1>EMR client</h1>
        </div>
        {token && (
          <button type="button" onClick={() => setToken('')}>
            Sign out
          </button>
        )}
      </header>
      {token ? (
        <Workspace token={token} onExpired={expire} />
      ) : (
        <section className="panel access">
          <h2>Connect to patient records</h2>
          <p>Enter your team API access token.</p>
          {message && <p role="alert">{message}</p>}
          <form onSubmit={start}>
            <label htmlFor="access-token">Access token</label>
            <input
              id="access-token"
              type="password"
              autoComplete="off"
              required
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="submit">Connect</button>
          </form>
        </section>
      )}
    </main>
  );
}

function Workspace({ token, onExpired }) {
  const [result, setResult] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const [patients, capability] = await Promise.all([
          fhirList('Patient', token, {}, controller.signal),
          fhirGet('metadata', token, controller.signal).catch((error) => {
            if (error.status === 403) return null; // Patient tokens cannot read metadata.
            throw error;
          }),
        ]);
        if (!controller.signal.aborted) {
          const available = capability?.rest?.flatMap((rest) =>
            rest.resource.map(({ type }) => type),
          );
          setResult({ patients, available });
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error.status === 401) onExpired();
        else setResult({ error: error.message });
      }
    }
    load();
    return () => controller.abort();
  }, [token, onExpired]);

  if (!result) return <p role="status">Loading patient records…</p>;
  if (result.error) return <p role="alert">{result.error}</p>;
  if (!result.patients.length) return <p>No patient profiles are available for this account.</p>;
  return <PatientRecords {...result} token={token} onExpired={onExpired} />;
}
