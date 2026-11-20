import { useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost/api/v1';

// PLACEHOLDER by Mazen: shows that the app can reach the API. Replace it.
export default function App() {
  const [status, setStatus] = useState('checking...');

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((response) => response.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus('unreachable'));
  }, []);

  return (
    <main style={{ fontFamily: 'Arial, sans-serif', padding: '2rem' }}>
      <h1>HCIS EMR Client (FHIR)</h1>
      <p>API status: {status}</p>
    </main>
  );
}
