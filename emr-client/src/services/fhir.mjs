const base = (import.meta.env?.VITE_EMR_API_BASE_URL || '/api/v1').replace(/\/+$/, '');

export async function fhirGet(path, token, signal) {
  const url = new URL(`${base}/fhir/${path}`, window.location.origin);
  const response = await fetch(url, {
    signal,
    redirect: 'error',
    headers: { Accept: 'application/fhir+json', Authorization: `Bearer ${token}` },
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    throw Object.assign(
      new Error(result?.issue?.[0]?.diagnostics ?? `Request failed (${response.status}).`),
      { status: response.status },
    );
  }
  if (!result?.resourceType) throw new Error('The server did not return a FHIR resource.');
  return result;
}

export async function fhirList(kind, token, filters = {}, signal) {
  const params = new URLSearchParams({ _count: '100', ...filters });
  const initial = new URL(`${base}/fhir/${kind}?${params}`, window.location.origin);
  const pages = new Set();
  const resources = [];
  let next = initial.href;
  while (next) {
    const url = new URL(next, initial);
    if (url.origin !== initial.origin || url.pathname !== initial.pathname || pages.has(url.href)) {
      throw new Error('The FHIR server returned an unexpected search link.');
    }
    for (const [name, value] of Object.entries(filters)) {
      if (url.searchParams.get(name) !== value) {
        throw new Error('The FHIR search link changed the selected patient.');
      }
    }
    pages.add(url.href);
    const bundle = await fhirGet(`${kind}${url.search}`, token, signal);
    if (bundle.resourceType !== 'Bundle' || bundle.type !== 'searchset') {
      throw new Error('The FHIR server did not return a search bundle.');
    }
    resources.push(...(bundle.entry ?? []).map(({ resource }) => resource));
    next = bundle.link?.find(({ relation }) => relation === 'next')?.url;
  }
  return resources;
}
